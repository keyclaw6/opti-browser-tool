# Draft Live-Site Testing Controls

**Status:** draft only. ADR-0006 is open. No live-site task is authorized by this document.

The project charter already requires permitted accounts, respect for platform rules and access controls, protection of credentials and sensitive data, and explicit control of destructive or externally visible actions. The detailed controls below are candidates for later review.

## Candidate controls

- The account is owned or explicitly permitted for testing.
- The task records platform, account alias, environment, permitted side effects, forbidden actions, teardown, and data-retention class.
- Credentials and session tokens are provided through a secret store and excluded from model-visible context and normal traces.
- The browser profile is isolated from personal browsing.
- Public or irreversible side effects are disabled by default.
- A task cannot bypass authentication, rate limits, access controls, CAPTCHAs, or platform restrictions.

## Candidate test design

Prefer reversible changes, drafts, private test groups, controlled recipient accounts, and synthetic content. Verify cleanup. Report live-site results separately because the environment is not fully reproducible.

## Candidate incident conditions

Unexpected external communication, public posting, purchase, account lockout, credential exposure, privacy leakage, failed cleanup, or action outside the allowlist should be treated as a safety incident rather than an ordinary executor failure.

These controls must be researched, tested in a safe environment, and explicitly approved before live-site execution.
