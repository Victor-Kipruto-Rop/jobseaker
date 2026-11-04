# Company identity, job ingestion and application history

## Product behavior

JobSeeker imports public vacancies from supported Greenhouse and Lever boards. It resolves the employer from the board's published identity, stores that employer as a reusable company record, and links imported opportunities and application history to it.

`Public ATS board → vacancy + employer metadata → normalized Company → Opportunity → Application snapshot → Dashboard`

Company records are reusable for multiple vacancies from the same board for the same account. Company records and linked opportunities are scoped to the owning candidate; the same public employer may have separate private records for different users.

## Supported public sources

- **Greenhouse:** public Job Board API for official board names and vacancy records; public board page for published company metadata.
- **Lever:** public postings feed for vacancy records; public employer board page for published company metadata.

This is source-specific integration, not a universal company crawler or a connector for every ATS provider.

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

A Company stores reusable employer identity and published brand metadata. Each CandidateOpportunity references a Company. The opportunity retains a copy of key company fields for stable listing and application rendering.

Company profile routes expose a user's own company records and linked roles only. Discovery cards and application records link to the company profile. The profile displays published website, source page, brand assets, description, industry, headquarters, social links, provenance and related roles.

## Vacancy refresh and availability

Each discovery run fetches the current source feed, resolves company metadata independently, updates existing vacancies, reactivates roles that reappear, inserts new roles, and skips duplicate source URLs. Company-page failure does not discard a successful job feed.

Migration `20261104_0011_opportunity_availability.py` adds availability state and last-seen timestamps. A listing is marked no longer listed only after a successful response smaller than the configured source limit. A full-limit response is not treated as a complete snapshot. Removed listings remain in the candidate's records rather than being deleted.

Saved-search automation refreshes employer identity and vacancy state per user. External requests are bounded and run outside database sessions. Failure on one board is isolated from other saved searches. New imports create in-app notifications.

## Application history snapshots

When a candidate creates an application from a linked opportunity, JobSeeker stores the original job description and a company profile snapshot. Application history therefore retains the employer branding and vacancy details that were available when the application was created, even if the source later edits or removes the listing.

Migration `20261104_0012_application_snapshots.py` adds these fields. Application creation and linked-opportunity lookup enforce owner boundaries.

## Limits and responsible use

- Only Greenhouse and Lever are currently supported for automated discovery.
- Only public board data and public page metadata are read.
- The system does not submit applications, contact recruiters, or bypass authentication or access controls.
- Some employers publish little or no structured metadata. The dashboard shows neutral fallbacks and discloses missing evidence.
- Skill extraction is a deterministic mention-based aid, not proof that every mentioned tool is mandatory.
- Work mode is inferred only from explicit source text or published workplace type; otherwise it remains unspecified.
- Industry, headquarters and social links may remain empty when the source does not publish reliable evidence.

## Verification gate

Run focused connector and automation tests, the full Python suite, Ruff, mypy, migration upgrades from the previous Phase 3 head and a clean database, frontend lint/build, and Docker Compose configuration/build. Then test authenticated Greenhouse and Lever imports, repeated discovery, removed/reappearing roles, company profile ownership, application snapshot persistence, and mobile/reduced-motion UI behavior.

Do not describe source review as a passing runtime test. Keep the pull request unmerged until CI and local integration checks have actual passing results.
