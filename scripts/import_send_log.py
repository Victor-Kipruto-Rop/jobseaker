import argparse
from pathlib import Path

from app.database import SessionLocal, init_db
from app.services.send_log_import import import_send_log


def main():
    parser = argparse.ArgumentParser(description="Preserve Gmail send-log rows and extract message/thread IDs.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.csv_path.is_file():
        parser.error(f"Send log not found: {args.csv_path}")
    init_db()
    with SessionLocal() as db:
        report = import_send_log(db, args.csv_path.read_bytes(), args.csv_path.name, dry_run=args.dry_run)
    print(report.as_dict())


if __name__ == "__main__":
    main()
