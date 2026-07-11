# ADR-0002: Shared substrate and lane boundaries

- Status: Open
- Date opened: 2026-07-11
- Approval state: Not accepted

## Question

How should visual-first, terminal/CLI, and later hybrid research be isolated while still producing comparable tasks, traces, metrics, and evaluator results?

## Candidate direction under consideration

One possible structure is a monorepo with narrow shared contracts and lane-specific adapters. Shared components could own task loading, environment setup, artifact storage, trace events, metrics, verifiers, and experiment records, while each lane owns its observations, actions, prompts, planning, recovery, and context management.

Another unresolved question is whether lanes should be represented by packages, configurations, short-lived experimental branches, separate repositories, or another mechanism.

This candidate direction is not active architecture.

## Research required

- Review how existing browser-agent harnesses isolate observation and action designs.
- Identify where shared abstractions helped comparison and where they constrained experiments.
- Compare repository and configuration structures used by the strongest candidate foundations.
- Test whether at least two contrasting lanes can share task and result contracts without leaking capabilities or forcing premature convergence.

## Decision gate

Accept an architecture only after the harness landscape review and a small compatibility prototype. Explicit project approval is required.
