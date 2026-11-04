"""Rewrap stored OAuth credentials with the active credential-vault key.

Run after adding the new key to JOBSEEKER_CREDENTIAL_KEYRING and setting
JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID. Retain old keys until this command reports
zero legacy/old-key records and backups have passed restore validation.
"""
from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from packages.database.sessions import SessionLocal
from packages.database.models.career import CalendarAccount, EmailAccount
from packages.security.credential_vault import (
    credential_key_id, decrypt_credential, rewrap_credential,
)


def rotate(dry_run: bool = False) -> dict[str, int]:
    counts = {"email_scanned": 0, "email_rotated": 0,
              "calendar_scanned": 0, "calendar_rotated": 0, "skipped_legacy": 0}
    with SessionLocal() as db:
        for model, purpose, scanned, rotated in (
            (EmailAccount, "gmail-oauth", "email_scanned", "email_rotated"),
            (CalendarAccount, "google-calendar", "calendar_scanned", "calendar_rotated"),
        ):
            rows = db.scalars(select(model).order_by(model.id)).all()
            for row in rows:
                counts[scanned] += 1
                token = row.encrypted_credentials
                try:
                    old_id = credential_key_id(token)
                except ValueError:
                    # Gmail's historical Fernet records are upgraded by the
                    # next successful mailbox sync, which still has the legacy reader.
                    counts["skipped_legacy"] += 1
                    continue
                plaintext = decrypt_credential(token, purpose=purpose)
                replacement = rewrap_credential(token, purpose=purpose)
                new_id = credential_key_id(replacement)
                if new_id != old_id:
                    if not dry_run:
                        row.encrypted_credentials = replacement
                    counts[rotated] += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotate JobSeeker OAuth credential envelopes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(rotate(dry_run=args.dry_run), indent=2))


if __name__ == "__main__":
    main()
