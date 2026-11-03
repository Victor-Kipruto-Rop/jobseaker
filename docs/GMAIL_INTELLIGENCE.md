# Gmail Intelligence: Initial Read-only Milestone

## Permission model
The first connector uses the Gmail `gmail.readonly` OAuth scope. It reads message metadata and Gmail snippets only. It does not send, mark read, archive, delete, or modify messages. Sending permissions are deliberately not requested in this milestone.

## Historic outreach
Import `outreach_send_log.csv` with the send-log importer first. It preserves every original row and extracts message and thread IDs from recognized columns. Unknown columns remain in `original_payload`. Exact message IDs are used to retrieve corresponding Gmail metadata.

## Job-related mailbox search
The initial query searches anywhere in the mailbox for job-related subject terms. Use `--query` to tune the Gmail search. Gmail search results are bounded by `--max-messages`; repeated syncs skip already stored message IDs.

## Local setup
1. Create a Google Cloud project and enable Gmail API.
2. Configure an OAuth Desktop application and download its client secret JSON to a private local path.
3. Set `GMAIL_ENABLED=true`, `GMAIL_CLIENT_SECRET_FILE` and `GMAIL_TOKEN_FILE` in local `.env`.
4. Install the requirements and run:

```powershell
python -m scripts.import_send_log "C:\\path\\to\\outreach_send_log.csv" --dry-run
python -m scripts.import_send_log "C:\\path\\to\\outreach_send_log.csv"
python -m scripts.sync_gmail --max-messages 500
```

OAuth token files and client secrets must never be committed.

## Classification limits
Initial classifications use deterministic phrase matching over the subject and Gmail snippet. They are triage labels, not definitive recruiter intent. Confidence values are heuristic. Full AI analysis, threading to application records, and user review controls are later milestones.
