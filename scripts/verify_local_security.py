from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "infrastructure" / "compose" / "docker-compose.yml"
LOCAL_DATABASE_URL = (
    "postgresql+psycopg://jobseeker:jobseeker_local@localhost:5432/jobseeker"
)
LOCAL_TEST_DATABASE_URL = LOCAL_DATABASE_URL


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def wait_for_api(url: str, timeout_seconds: int = 240) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=3) as response:
                if response.status == 200:
                    print(f"API readiness confirmed: {url}", flush=True)
                    return
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(3)
    raise RuntimeError(f"API did not become healthy within {timeout_seconds}s: {last_error}")


def _local_secret() -> str:
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "APP_SECRET_KEY":
            return value.strip().strip('"').strip("'")
    return ""


def main() -> int:
    if not (ROOT / ".env").exists():
        print(
            "Missing repository .env. Copy .env.example to .env and keep all values local.",
            file=sys.stderr,
        )
        return 2

    secret = _local_secret()
    if len(secret) < 32 or "replace-with" in secret.lower() or "change-me" in secret.lower():
        print("Set a unique local APP_SECRET_KEY of at least 32 characters in .env.", file=sys.stderr)
        return 2

    compose = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    pnpm = "pnpm.cmd" if os.name == "nt" else "pnpm"
    local_env = os.environ.copy()
    local_env.update(
        {
            "APP_ENV": "local",
            "ADMIN_BOOTSTRAP_ENABLED": "false",
            "APP_SECRET_KEY": secret,
            "AI_DEFAULT_PROVIDER": "mock",
            "AI_FALLBACK_PROVIDER": "mock",
            "OPENAI_ENABLED": "false",
            "OPENAI_API_KEY": "",
            "ANTHROPIC_ENABLED": "false",
            "ANTHROPIC_API_KEY": "",
            "SMTP_HOST": "",
            "SMTP_USERNAME": "",
            "SMTP_PASSWORD": "",
            "SMTP_FROM_EMAIL": "",
            "GMAIL_CLIENT_SECRET_FILE": "",
            "DATABASE_URL": LOCAL_DATABASE_URL,
            "JOBSEEKER_TEST_DATABASE_URL": LOCAL_TEST_DATABASE_URL,
            "REDIS_URL": "redis://localhost:6379/0",
            "GLOBAL_AUTOMATION_PAUSED": "true",
            "AUTO_EMAIL_SEND": "false",
            "AUTO_APPLICATION_SUBMIT": "false",
            "GMAIL_ENABLED": "false",
            "JOB_DISCOVERY_ENABLED": "false",
        }
    )

    try:
        run(compose + ["config", "--quiet"], env=local_env)
        run(compose + ["up", "--build", "-d"], env=local_env)
        wait_for_api("http://127.0.0.1:8000/health/ready")
        wait_for_api("http://127.0.0.1:3000")

        service_status = subprocess.run(
            compose + ["ps", "--services", "--status", "running"],
            cwd=ROOT,
            env=local_env,
            check=True,
            capture_output=True,
            text=True,
        )
        running = set(service_status.stdout.split())
        required = {"postgres", "redis", "api", "web", "worker", "scheduler"}
        missing = sorted(required - running)
        if missing:
            raise RuntimeError("Local Compose services are not running: " + ", ".join(missing))

        run([sys.executable, "-m", "compileall", "-q", "apps", "packages", "tests", "migrations", "scripts"], env=local_env)
        run(["alembic", "upgrade", "head"], env=local_env)
        run(["alembic", "check"], env=local_env)
        run([sys.executable, "-m", "pytest", "-q"], env=local_env)
        run(["ruff", "check", "."], env=local_env)
        run([pnpm, "lint"], cwd=ROOT / "apps" / "web", env=local_env)
        run([pnpm, "build"], cwd=ROOT / "apps" / "web", env=local_env)
        run(compose + ["ps"], env=local_env)
    except subprocess.CalledProcessError as exc:
        print(
            f"Verification failed with exit code {exc.returncode}. "
            "The local stack is intentionally left running for inspection.",
            file=sys.stderr,
        )
        return exc.returncode or 1
    except Exception as exc:
        print(
            f"Verification failed: {exc}. The local stack is intentionally left running for inspection.",
            file=sys.stderr,
        )
        return 1

    print(
        "Local verification completed. The stack remains running. "
        "Stop it with: docker compose -f infrastructure/compose/docker-compose.yml down",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
