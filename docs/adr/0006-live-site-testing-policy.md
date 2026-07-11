# ADR-0006: Live-site testing isolation and safety

- Status: Open
- Date opened: 2026-07-11
- Approval state: Not accepted

## Question

What detailed operating policy, account isolation, evidence handling, side-effect controls, and incident process are required before testing on permitted live platforms?

## Accepted constraints from the charter

Live-platform testing must use permitted accounts, respect platform rules and access controls, protect credentials and sensitive data from model-visible traces, and explicitly control destructive or externally visible actions.

Those constraints do not yet settle the implementation policy.

## Candidate controls to investigate

Possible controls include isolated profiles, secret references rather than embedded credentials, task-specific side-effect allowlists, reversible/private actions, separate live-site reporting, teardown checks, redaction, restricted artifact storage, and explicit incident classification.

## Research required

- Review the operational and safety practices of existing live-site browser-agent projects and benchmarks.
- Define task impact tiers, authorization boundaries, teardown guarantees, and prohibited actions.
- Decide how account state, rate limits, policy changes, and nondeterminism affect evaluation validity.
- Test credential redaction and failure containment on a non-public or replica environment before any live pilot.

## Decision gate

No live-site task may run until the detailed policy, account plan, artifact controls, and incident procedure are explicitly approved.
