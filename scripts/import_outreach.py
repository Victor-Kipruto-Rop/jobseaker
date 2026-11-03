import argparse
from pathlib import Path

from app.database import SessionLocal, init_db
from app.services.outreach_import import import_outreach_csv


def main():
    parser = argparse.ArgumentParser(description="Import existing outreach CSV without modifying the source file.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.csv_path.is_file():
        parser.error(f"CSV file not found: {args.csv_path}")

    init_db()
    with SessionLocal() as db:
        report = import_outreach_csv(db, args.csv_path.read_bytes(), dry_run=args.dry_run)
    print(report.as_dict())


if __name__ == "__main__":
    main()
