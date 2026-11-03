import subprocess
import sys

def run(label, command):
    print(f"\n== {label} ==")
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)

def main():
    run("Python compile", [sys.executable, "-m", "compileall", "-q", "apps", "packages", "tests"])
    run("Python tests", [sys.executable, "-m", "pytest", "-q"])
    run("Python lint", ["ruff", "check", "."])
    print("\nLocal verification completed. Run 'cd apps/web && pnpm lint && pnpm build' for frontend checks.")

if __name__ == "__main__":
    main()
