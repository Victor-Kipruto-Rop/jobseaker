# Safe Automation Policy

## Defaults

- Gmail integration disabled until OAuth is configured.
- Gmail starts read-only.
- Job discovery disabled until compliant source connectors are configured.
- Automatic application submission disabled.
- Global automation pause enabled.

## Automatic submission eligibility

A future submission may proceed only if all conditions are true:
1. Global pause is off and automatic submission is explicitly enabled.
2. At least one enabled rule approved by the user matches the vacancy.
3. The role, location, match score and other configured constraints pass.
4. Required screening answers are known, factual and verified.
5. The approved CV/document version exists.
6. The application adapter is supported and permitted.
7. No duplicate application exists.
8. The portal does not require an unhandled CAPTCHA, 2FA challenge, legal declaration, sensitive disclosure or unknown commitment.

If any check fails, create a pending approval instead. Never guess candidate facts, bypass access controls, or claim a submission succeeded without a confirmation receipt.

## Email truthfulness

A Gmail Sent record indicates Gmail accepted the send operation. It does not prove delivery, reading, or that a recruiter viewed the message. Record replies and bounces as separate observed events.
