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

Create a saved search using POST /api/v1/saved-searches. The local scheduler refreshes saved searches every six hours and creates in-app notifications when new roles are found. Scheduled discovery is paused by default. Set JOB_DISCOVERY_ENABLED=true and GLOBAL_AUTOMATION_PAUSED=false in your local .env to opt in after reviewing the configured saved searches. Both settings are required: the first enables the discovery feature, and the second releases the global automation pause. The scheduler and worker containers read these settings from the same environment file.

## Scoring

The current fit score is a transparent keyword baseline against skills recorded in the candidate profile. It is not a predictive hiring probability or a commercial ATS score. Users should inspect the original listing and verify all requirements.


## Search filters

Saved searches and one-off discovery requests support:
- keywords: up to 20 terms. A role is retained when its title or description contains at least one configured term (case-insensitive).
- location: optional substring matched against the normalized location and description.
- remote_only: retains roles whose title, description, or location explicitly signals remote, distributed, work-from-home, or anywhere.

These are deterministic text filters, not semantic search. Source results are normalized first, then filters are applied before persistence. The scheduled worker reads the same saved-search filters as manual discovery. Empty filters preserve all source results.

Opportunity URLs are unique per user. The database enforces this with a partial unique index while allowing multiple manually entered opportunities without a source URL. Migration 20261103_0007 checks for existing duplicates and stops with a remediation message instead of deleting candidate data.
