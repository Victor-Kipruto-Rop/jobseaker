import argparse
import sys

from apps.api.app.core.config import get_settings
from packages.database.sessions import SessionLocal
from packages.security.rbac import set_user_role


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Operator-only candidate/admin role assignment."
    )
    parser.add_argument("--email", required=True, help="Exact target account email.")
    parser.add_argument("--role", required=True, choices=("candidate", "admin"))
    parser.add_argument("--operator", required=True, help="Audited operator identity.")
    parser.add_argument("--confirm-email", required=True, help="Repeat the exact target email.")
    args = parser.parse_args()

    if not get_settings().admin_bootstrap_enabled:
        print("Refusing role change: ADMIN_BOOTSTRAP_ENABLED must be true.", file=sys.stderr)
        return 2
    if args.email.strip().lower() != args.confirm_email.strip().lower():
        print("Refusing role change: confirmation email does not match.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        user = set_user_role(
            db,
            email=args.email,
            role=args.role,
            operator=args.operator,
        )
        print(f"Updated {user.email}: role={user.role}")
        return 0
    except (ValueError, LookupError) as exc:
        db.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
