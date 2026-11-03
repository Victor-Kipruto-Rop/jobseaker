from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from apps.api.app.core.config import get_settings
from packages.database.models.career import AuditLog
from packages.database.models.identity import User
from packages.database.sessions import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote an existing JobSeeker account to administrator."
    )
    parser.add_argument("--email", required=True, help="Exact email address of the existing account.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm this privileged role change and write an audit event.",
    )
    args = parser.parse_args()

    if not get_settings().admin_bootstrap_enabled:
        print("Refusing role change: set ADMIN_BOOTSTRAP_ENABLED=true for this one operation.", file=sys.stderr)
        return 2
    if not args.confirm:
        print("Refusing role change: pass --confirm after verifying the account.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()).with_for_update())
        if user is None:
            print("No account found for the supplied email.", file=sys.stderr)
            return 1
        if not user.is_active:
            print("Refusing role change for an inactive account.", file=sys.stderr)
            return 1
        if user.role == "admin":
            print("Account is already an administrator.")
            return 0

        user.role = "admin"
        db.add(AuditLog(
            user_id=user.id,
            action="security.role_promoted",
            resource_type="user",
            resource_id=str(user.id),
            metadata_json={"previous_role": "candidate", "new_role": "admin", "method": "operator_cli"},
        ))
        db.commit()
        print(f"Promoted account {user.email} to administrator. Disable ADMIN_BOOTSTRAP_ENABLED now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
