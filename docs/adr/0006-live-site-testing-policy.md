# ADR-0006: Live-site testing isolation and safety

- Status: Proposed
- Date proposed: 2026-07-11

## Context

Real social and dynamic platforms are important, but they create account, privacy, policy, nondeterminism, and irreversible-side-effect risks that ordinary benchmark replicas do not.

## Decision

Keep live-site suites outside default CI and require an explicit opt-in profile. Use permitted accounts, documented platform constraints, isolated browser profiles, secret references instead of embedded credentials, and task-specific side-effect allowlists.

Prefer dedicated test communities, drafts, private messages to controlled accounts, and reversible changes. Posting publicly, sending unsolicited messages, changing security settings, purchasing, deleting user data, or bypassing access controls is prohibited unless a separately reviewed task explicitly authorizes the exact action and provides safe cleanup.

Redact credentials, private messages, personal identifiers, session tokens, and sensitive screenshots before judge or optimizer access. Keep raw restricted artifacts under a separate retention and access policy.

Each task defines setup, permitted side effects, forbidden actions, teardown, and a maximum impact tier. A failed or interrupted teardown is surfaced as a safety incident, not hidden as a normal task failure.

## Alternatives considered

- Treat live sites like ordinary benchmarks: operationally convenient but unsafe and irreproducible.
- Avoid live sites entirely: safer but misses compatibility and session-state failures central to the research goal.

## Consequences

Live results are reported separately from deterministic replicas. Some tasks require human account preparation or review. Safety and platform-policy violations cannot be traded for higher task success.

## Validation and revisit trigger

Run an initial pilot only on reversible, private actions. Revisit after the project has proven credential redaction, teardown, and incident reporting.
