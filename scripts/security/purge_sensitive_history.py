#!/usr/bin/env python3
"""Prepare or manually execute the repository's sensitive-history purge.

Run the dry-run first. Execute only in a fresh backup clone after reviewing the
owner checklist in docs/security/HISTORY_PURGE_CHECKLIST.md. This script never
pushes or force-pushes refs.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATHS = (
    "secrets/",
    "data/private/",
    "kenya_data_opportunities_contacts.csv",
    "reconciled_outreach_contacts.csv",
    "outreach_send_log.csv",
    "outreach_reconciliation_report.md",
    "historical_sacco_verification.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="run git-filter-repo; without this flag only print the exact command",
    )
    args = parser.parse_args()

    if not (ROOT / ".git").exists():
        print("Run this script from a normal Git working tree.", file=sys.stderr)
        return 2
    if not shutil.which("git"):
        print("Git is required.", file=sys.stderr)
        return 2
    version = subprocess.run(
        ["git", "filter-repo", "--version"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if version.returncode:
        print("git-filter-repo is not installed. See the owner checklist.", file=sys.stderr)
        return 2

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        print("Refusing to rewrite a dirty working tree. Use a fresh backup clone.", file=sys.stderr)
        return 2

    command = ["git", "filter-repo", "--invert-paths"]
    for path in PATHS:
        command.extend(["--path", path])

    print("Prepared history-rewrite command (no push will be performed):")
    print(" ".join(command))
    if not args.execute:
        print("Dry run only. Review docs/security/HISTORY_PURGE_CHECKLIST.md before --execute.")
        return 0

    print("Executing destructive local history rewrite in this clone.", file=sys.stderr)
    subprocess.run(command, cwd=ROOT, check=True)
    print("Local history rewrite finished. Verify every ref and scan again before any push.")
    print("git-filter-repo may remove the origin remote. No remote push was attempted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
