from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from packages.database.models.career import AuditLog
from packages.database.models.identity import User
from packages.database.sessions import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote an existing verified JobSeeker account to administrator."
    )
    parser.add_argument("--email", required=True, help="Exact email address of the existing account")
    parser.add_argument(
        "--confirm-email",
        required=True,
        help="Repeat the exact email to confirm this privileged operation",
    )
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not email or email != args.confirm_email.strip().lower():
        parser.error("--email and --confirm-email must match exactly")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email).with_for_update())
        if user is None:
            print("No account found. Register and verify the account before promotion.", file=sys.stderr)
            return 2
        if not user.is_active or not user.is_verified:
            print("Only active, email-verified accounts can be promoted.", file=sys.stderr)
            return 2
        if user.role == "admin":
            print(f"{email} is already an administrator.")
            return 0

        print("PRIVILEGED ACTION: this changes the account role to administrator.")
        typed = input(f"Type the exact email ({email}) to continue: ").strip().lower()
        if typed != email:
            print("Confirmation did not match; no changes made.", file=sys.stderr)
            return 2

        user.role = "admin"
        db.add(AuditLog(
            user_id=user.id,
            action="security.admin_role_granted",
            resource_type="user",
            resource_id=str(user.id),
            metadata_json={"provisioned_by": "interactive_operator_cli"},
        ))
        db.commit()
        print(f"Administrator role granted to {email}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
