from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.app.core.config import get_settings  # noqa: E402
from packages.database.sessions import SessionLocal  # noqa: E402
from packages.security.rbac import set_user_role  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote an existing active, verified JobSeeker account to administrator."
    )
    parser.add_argument("--email", required=True, help="Exact target account email.")
    parser.add_argument("--operator", required=True, help="Audited operator identity.")
    parser.add_argument("--confirm-email", required=True, help="Repeat the exact target email.")
    args = parser.parse_args()

    if not get_settings().admin_bootstrap_enabled:
        print("Refusing role change: ADMIN_BOOTSTRAP_ENABLED must be true.", file=sys.stderr)
        return 2
    if args.email.strip().lower() != args.confirm_email.strip().lower():
        print("Refusing role change: confirmation email does not match.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        try:
            user = set_user_role(
                db, email=args.email, role="admin", operator=args.operator,
            )
        except (ValueError, LookupError) as exc:
            db.rollback()
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Promoted {user.email} to administrator. Disable ADMIN_BOOTSTRAP_ENABLED now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
