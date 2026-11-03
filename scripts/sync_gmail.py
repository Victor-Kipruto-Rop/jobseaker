import argparse

from app.database import SessionLocal, init_db
from app.email_intelligence.gmail import DEFAULT_QUERY, sync_job_related_mail


def main():
    parser = argparse.ArgumentParser(description="Read-only sync of job-related Gmail metadata.")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--max-messages", type=int, default=500)
    args = parser.parse_args()
    if args.max_messages < 1 or args.max_messages > 5000:
        parser.error("--max-messages must be between 1 and 5000")
    init_db()
    with SessionLocal() as db:
        print(sync_job_related_mail(db, query=args.query, max_messages=args.max_messages))


if __name__ == "__main__":
    main()
