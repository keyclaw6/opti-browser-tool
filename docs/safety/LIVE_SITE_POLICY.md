# Live-Site Testing Policy

This policy applies to Reddit, Facebook, LinkedIn, and other real platforms.

## Required controls

- The account is owned or explicitly permitted for testing.
- The task records platform, account alias, environment, permitted side effects, forbidden actions, teardown, and data-retention class.
- Credentials and session tokens are provided through a secret store and excluded from model-visible context and normal traces.
- The browser profile is isolated from personal browsing.
- Public or irreversible side effects are disabled by default.
- A task cannot bypass authentication, rate limits, access controls, CAPTCHAs, or platform restrictions.

## Preferred test design

Use reversible changes, drafts, private test groups, controlled recipient accounts, and synthetic content. Verify cleanup. Report live-site results separately because the environment is not fully reproducible.

## Incident conditions

Unexpected external communication, public posting, purchase, account lockout, credential exposure, privacy leakage, failed cleanup, or action outside the allowlist is a safety incident. Stop the affected run, preserve restricted evidence, and do not classify it as an ordinary executor failure.
