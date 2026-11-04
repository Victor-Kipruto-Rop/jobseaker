# JobSeeker Intelligence frontend

## Product direction

JobSeeker Intelligence is a personal career operations product. The interface is designed around five primary destinations rather than a collection of loosely connected tools:

- **Overview**: account-backed career metrics, application pipeline, attention queue, recent activity and strongest saved skill matches.
- **Opportunities**: Greenhouse and Lever board discovery, reusable saved searches, a private saved-role library, skill-fit evidence and application draft creation.
- **Applications**: application records, stage transitions, notes, original listing links, explicit submission approval requests and a decision queue.
- **Career profile**: professional identity, skill proficiency and evidence, private CV library, transparent keyword coverage and an integrated AI career studio for CV tailoring, cover letters, interview preparation and skills roadmaps.
- **Settings**: account verification, AI token budget controls, Gmail read-only connection, synchronization, recent message summaries, disconnect controls and sign-out.

The notification bell is a contextual control. Approval requests are part of the Applications destination. Former standalone routes redirect to their relevant consolidated destination so existing links do not become dead ends.

## Visual system

- Light mode only. No dark theme or dark-mode preference.
- Warm off-white application canvas (#F5F6F2), white work surfaces, muted forest-green actions and restrained brass highlights.
- Editorial serif page headings paired with compact sans-serif controls and data labels.
- Refined fixed desktop sidebar, compact account switcher, grouped navigation, active route marker, pending-approval count, responsive mobile drawer and sticky workspace header.
- Tables, status labels, data rows and forms are deliberately compact and legible. Avoid decorative metric cards, exaggerated gradients, fake charts and unnecessary navigation.
- Keyboard-visible focus, semantic page landmarks, accessible labels, responsive layouts and reduced-motion support.

## Backend integration

The UI uses the existing FastAPI routes and cookie-based session model. Requests include credentials, and state-changing requests send the CSRF token from the session cookie.

| Workspace | Backend routes |
|---|---|
| Overview | /auth/me, /applications, /opportunities, /analytics/overview, /profile, /automations/approvals, /notifications |
| Opportunities | /opportunities, /opportunities/discover, /saved-searches, /applications |
| Applications | /applications, /applications/{id}, /automations/approvals, /automations/approvals/{id}/decision |
| Career profile | /profile, /profile/skills, /resumes, /resumes/{id}/analyze, /career-tools/*, /career-tools/artifacts/* |
| Settings | /auth/me, /auth/verification/request, /ai/budget, /integrations/gmail/account, /integrations/gmail/authorize, /integrations/gmail/sync, /auth/logout |
| Notifications | /notifications, /notifications/{id}/read |

The UI preserves backend ownership boundaries. It does not trust browser-supplied account IDs to scope records.

## Safety and data integrity

- All displayed metrics are derived from the authenticated account's API records.
- Skill-fit and CV keyword coverage are presented as heuristics, not hiring probabilities or commercial ATS scores.
- AI generation only occurs after an explicit user action, is subject to the configured provider and token budget, and produces editable draft artifacts.
- AI artifacts are not automatically emailed, submitted or sent to an employer.
- Application submission approval records the user's decision. It does not submit an application externally.
- Gmail authorization is checked to ensure it requests gmail.readonly; the browser does not receive provider credentials.
- Resume uploads are limited by the existing backend to PDF/DOCX, 10 MB and safe text extraction. The existing backend intentionally disables resume upload in production until private object storage is configured; the UI surfaces that backend response rather than bypassing it.
- No production deployment, external email sending or automatic application submission is part of this change.

## Consolidated route map

- /dashboard is the overview.
- /opportunities combines discovery, saved searches and saved roles.
- /applications combines tracking and approval decisions.
- /profile combines profile, skills, CV library, ATS keyword coverage and AI career drafts.
- /settings combines account, AI budget and Gmail integration controls.
- /discovery, /companies and /recruiters redirect to /opportunities.
- /approvals and /interviews redirect to the relevant Applications view.
- /cv-studio, /career-studio and /intelligence redirect to /profile.
- /inbox redirects to Settings, where Gmail is connected and managed.
- /notifications redirects to Overview; notifications are available from the header bell.
- /analytics redirects to Overview, where account-backed analytics are presented.

## Verification status

Implementation is committed to phase-3-frontend-experience. GitHub API writes confirm the branch files were updated, but this is not proof of a successful local Next.js build or browser behavior. A local pnpm --filter web lint, pnpm --filter web build, authenticated API smoke test, responsive browser review and accessibility review must still be run against the completed branch. Record their actual outputs in docs/VERIFICATION.md before declaring the phase complete.

## Environment-dependent capabilities

- Job discovery requires the backend JOB_DISCOVERY_ENABLED setting and supported public board identifiers.
- AI draft generation requires a configured server-side AI provider and available account token budget.
- Gmail requires a verified account and configured Google OAuth credentials. It requests read-only scope only.
- Production resume uploads remain unavailable until private object storage is configured.
