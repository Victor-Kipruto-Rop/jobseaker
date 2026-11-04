# Company identity, job ingestion and application history

## Product behavior

JobSeeker imports public vacancies from supported Greenhouse and Lever boards. It resolves the employer from the board's published identity, stores that employer as a reusable company record, and links imported opportunities and application history to it.

The data flow is:

`Public ATS board → vacancy + employer metadata → normalized Company → Opportunity → Application snapshot → Dashboard`

The company profile is reused by multiple vacancies from the same board for the same account. Company records and linked opportunities are scoped to the owning candidate; the same public employer may have separate private records for different users.

## Supported public sources

- **Greenhouse:** public Job Board API for official board names and vacancy records; public board page for published company metadata.
- **Lever:** public postings feed for vacancy records; public employer board page for published company metadata.

The integration is intentionally source-specific. It does not claim to be a universal company crawler or a connector for every ATS provider.

## Company metadata imported when published

- Official board/employer name where exposed by the Greenhouse API or page metadata.
- Canonical company website and domain when the canonical URL points to a non-ATS host.
- Open Graph/Twitter image or an HTML image fallback for a company logo.
- Published favicon as a secondary icon.
- Public description, industry, headquarters/locality and theme color when exposed.
- Public LinkedIn, X, GitHub, Facebook, YouTube and Instagram links found on the board page.
- Source provider, board slug, source URL, last enrichment time and a record of which fields were actually published.

Only HTTPS URLs are accepted for displayed company assets, websites and social links. Metadata values are bounded and validated. A page favicon may be ATS-branded; it is treated as an icon fallback, not proof of an official company logo. A canonical URL is provenance evidence, not legal verification of the company.

Missing data remains missing. The interface uses a neutral monogram/icon fallback rather than fabricating company assets or substituting a different employer's brand.

## Reusable company data model

Migration `20261104_0010_company_entities.py` adds the company relationship and source identity fields. Existing saved opportunities are backfilled into user-owned legacy company records during migration, so older imported roles are not left orphaned.

A Company stores the reusable employer identity and published brand metadata. Each CandidateOpportunity references a Company. The opportunity retains a copy of key company fields for stable listing and application rendering.

Company profile routes expose a user's own company records and linked roles only. Discovery cards and application records link to the company profile. The profile displays published website, source page, brand assets, description, industry, headquarters, social links, provenance and related roles.

## Vacancy refresh and availability

Every discovery run:
1. Fetches the source board's current vacancy feed.
2. Resolves company metadata independently; company-page failure does not discard a successful job feed.
3. Updates already imported vacancies from the source without replacing user-owned application history.
4. Re-activates roles that have reappeared.
5. Inserts newly discovered roles and skips duplicate source URLs.
6. Marks previously imported roles as no longer listed only after a successful response that is smaller than the configured source limit. A full-limit response is not treated as a complete snapshot.
7. Records the latest sighting time and sends an in-app notification when new roles are added.

Migration `20261104_0011_opportunity_availability.py` adds availability state and last-seen timestamps. A removed listing is retained in the user's records; it is not deleted.

## Application history snapshots

When a candidate creates an application from a linked opportunity, JobSeeker stores the original job description and a company profile snapshot. The application therefore retains the employer branding and vacancy details that were available when the application was created, even if the source later edits or removes the listing.

Migration `20261104_0012_application_snapshots.py` adds these fields. Application creation and linked-opportunity lookup enforce owner boundaries. Application history can show the saved original description without relying on the live source record.

## Automation behavior

Saved-search discovery refreshes employer identity and vacancy state for each saved Greenhouse or Lever board. External requests are bounded and performed outside database sessions. A failure on one board is isolated from other saved searches. Employer profile enrichment is best-effort; a valid vacancy feed can still be imported when the employer page is unavailable.

## Limits and responsible use

- Only Greenhouse and Lever are currently supported for automated discovery.
- Only public board data and public page metadata are read.
- The system does not submit applications, contact recruiters, or bypass authentication or access controls.
- Some employers publish little or no structured metadata. The dashboard must show neutral fallbacks and disclose missing evidence.
- Skill extraction is a deterministic mention-based aid, not proof that every mentioned tool is mandatory.
- Work mode is inferred only from explicit source text or published workplace type; otherwise it remains unspecified.
- Industry, headquarters and social links may remain empty when the source does not publish reliable evidence.

## Verification gate

Run the focused connector tests, the full Python suite, Ruff, mypy, migration upgrade from both the previous Phase 3 head and a clean database, frontend lint/build, and the Docker Compose configuration/build. Then test authenticated Greenhouse and Lever imports, repeated discovery, removed/reappearing roles, company profile ownership, application snapshot persistence, and mobile/reduced-motion UI behavior.

No source review should be described as a passing runtime test. Keep the pull request unmerged until CI and local integration checks have actual passing results.
