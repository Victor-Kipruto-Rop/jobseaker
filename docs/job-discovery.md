# Job discovery

## Supported connectors

JobSeeker currently supports public job-board APIs for:

- Greenhouse: https://boards-api.greenhouse.io/v1/boards/{board}/jobs
- Lever: https://api.lever.co/v0/postings/{site}?mode=json

The board identifier must be a simple slug. The integration does not accept arbitrary URLs, reducing SSRF risk.

## Manual discovery

Use POST /api/v1/opportunities/discover with an authenticated session:

- source: greenhouse or lever
- board: public board identifier
- company_name: optional display name
- limit: 1 to 100

Imported roles are stored per user and deduplicated by source URL.

## Recurring discovery

Create a saved search using POST /api/v1/saved-searches. The local scheduler refreshes saved searches every six hours and creates in-app notifications when new roles are found.

## Scoring

The current fit score is a transparent keyword baseline against skills recorded in the candidate profile. It is not a predictive hiring probability or a commercial ATS score. Users should inspect the original listing and verify all requirements.
