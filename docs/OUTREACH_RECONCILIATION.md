# Outreach and Send-log Reconciliation

The importer stores source rows as received and does not edit the source CSV. It retains unknown columns in JSON so the actual send-log schema can be reconciled without losing data.

## Import order

1. Back up the original CSV and send log outside the repository.
2. Run a dry-run import of the contact CSV.
3. Import the contact CSV.
4. Run a dry-run import of the send log.
5. Import the send log.
6. Review the counts for total rows, inserted rows, existing rows, message IDs and thread IDs.
7. Run read-only Gmail sync to fetch metadata for known message IDs and job-related conversations.

## Stable source identity

Send-log rows are scoped by the source filename and identified by row number plus original field values. Re-running the same unchanged file is idempotent. Keep the original filename stable when importing later appended versions. The importer retains all original field values.

## Reconciliation still required

The import does not automatically equate an outreach row with a send-log row based only on company-name similarity. Matching uses exact Gmail IDs first; organization/email/date matching will be reviewed as a separate reconciliation step with confidence and evidence.
