# Company identity and brand enrichment

## Purpose

Opportunity discovery must preserve the identity of the employer that published a role. The dashboard must not invent company names, fabricate logos, or display the ATS provider's generic brand as the employer's logo.

## Current ingestion sources

- Greenhouse public Job Board API supplies the official public board name and published job records. The integration reads the public board metadata endpoint and the public board page.
- Lever public postings feed supplies job records. The integration inspects the public employer board page for its published site identity and brand metadata.

The implementation extracts available Open Graph / Twitter metadata, the page title when it is not a generic careers title, canonical URL, logo image and favicon. It only accepts HTTPS URLs for displayed company assets and website links. It does not submit applications to ATS providers.

## Persisted opportunity company fields

- `company`: resolved board name, unless the user explicitly overrides the display name in the discovery form.
- `company_website` and `company_domain`: populated only when the public board exposes a non-ATS canonical company URL.
- `company_logo_url`: published Open Graph / Twitter image when available.
- `company_favicon_url`: published page icon when available.
- `company_description`: public board description metadata when available.
- `company_brand_source`: source board page used to obtain the metadata.

Migration: `20261104_0009_company_branding.py`.

## Dashboard behavior

- Opportunity and saved-role cards display the imported logo or favicon when available.
- Application records inherit company branding from their linked, user-owned opportunity.
- Discovery shows the resolved employer identity, website/domain evidence and whether a published brand asset was found.
- Re-running a board search backfills missing company metadata on previously imported roles without overwriting non-empty user/company fields.
- Missing company assets use a neutral visual fallback. No generated or guessed logo is substituted.

## Data quality and limitations

Company pages do not publish every field consistently. A missing logo, official website or description remains missing rather than being fabricated. A canonical URL is evidence of the page's canonical location, not a guarantee of legal corporate identity. The ATS favicon may be provider-branded; treat it as a fallback icon, not proof of an official company logo.

The current discovery providers remain Greenhouse and Lever. Other ATS providers and broad web-wide company discovery require separate connectors and source-specific validation. This feature imports only public data exposed by the selected board and does not crawl private pages, bypass access controls, or collect personal recruiter data.

## Verification required

Run `pytest -q tests/unit/test_job_discovery_filters.py`, the full Python test suite, Ruff, mypy, Alembic upgrade from the previous head, frontend lint/build, and authenticated end-to-end discovery against real public Greenhouse and Lever boards. Confirm that missing assets render the neutral fallback and that application records only expose branding from the current user's linked opportunity.
