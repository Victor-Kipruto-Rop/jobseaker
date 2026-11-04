# Frontend design and experience direction

## Product positioning

JobSeeker Intelligence is a career operations workspace, not a generic job-board clone. The interface should help a user move from opportunity discovery to informed application decisions while keeping external actions under explicit user control.

## Visual system

- Deep charcoal and forest surfaces with restrained mint-green accents.
- Compact information hierarchy, readable data density and clear page-level actions.
- System sans-serif typography with a restrained display stack. No runtime dependency on a remote font service.
- Thin borders, low-contrast surfaces and limited gradients. Avoid oversized empty cards and decorative dashboard metrics.
- Responsive desktop sidebar, mobile navigation drawer and consistent workspace header.
- Keyboard-visible focus, semantic landmarks, accessible labels and reduced-motion support.

## Dashboard composition

1. Page heading and primary actions for discovery and application tracking.
2. Email verification notice when the authenticated account is not verified.
3. Four account-backed metrics: saved opportunities, applications, interviews and recorded AI tokens.
4. Application pipeline derived from the authenticated user's actual application status counts.
5. Next-best-move prompts derived from the user's actual saved applications and opportunities.
6. Recent applications from the authenticated user's application records.
7. Strongest saved opportunity ranked only by the existing recorded skill-fit score.

No fabricated response rates, salary estimates, market trends, application history or AI insights are displayed. Empty states explain the next useful action.

## Safety and integration constraints

- API calls remain configurable through NEXT_PUBLIC_API_BASE_URL.
- Authenticated requests continue to send cookies and CSRF headers.
- No live AI provider calls are introduced by the dashboard.
- AI-generated content remains draft-only.
- Email sending and application submission remain disabled unless the existing explicit approval flow is used.
- No production deployment or external account writes are part of this change.

## Scope and verification

This branch establishes the shared workspace shell across the authenticated application routes, the redesigned dashboard and the public landing page. The route-specific forms, tables and content panels still need a visual and interaction pass so each workflow reaches the same level of polish as the dashboard.

The code has been committed through GitHub. A local Next.js build, browser review, accessibility audit and responsive-device verification have not yet been run in this environment. These must be completed by the repository owner before this phase is considered verified.
