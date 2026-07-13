# Open Questions

These are intentionally unresolved. They should be answered through research and explicit decisions rather than incidental implementation choices.

1. Which saved and external browser-agent repositories belong in the first harness survey?
2. Which existing harness or combination of components should be the first experimental baseline?
3. Which browser engine, control layer, and action mechanisms should that baseline use?
4. How should visual-first, terminal/CLI, and later hybrid research be isolated?
5. Should ADR-0008's proposed source allocation be accepted, revised, or rejected after task-level evidence is available?
6. Which REAL task version—v1, v2, or a pinned mixture—has suitable programmatic action evaluators and published-score comparability?
7. Which of the 140 selected provisional candidates are runnable, safely usable, nonduplicative, stable, inside the 35–70% task-level band, and backed by reliable verifiers?
8. Can WebChoreArena evaluators be independently audited or ported to verified semantics, and can up to five WebForge Level 3 tasks be made deterministic?
9. Which of the 20 selected WARC-Bench candidates survive replay setup, verifier audit, duplication analysis, and task-level calibration?
10. Do EntWorld or RiskWebWorld obtain authoritative public releases that justify replacing part of WorkArena++, WebForge, or another allocated source?
11. When ADR-0006 is ready, should WebSP-Eval become the first permitted-account configuration and privacy transfer suite?
12. Which of the current 20 smoke candidates remain stable after real environment and verifier validation?
13. How should unstable tasks, repeated trials, initial regression membership, later regression promotion, and the hidden holdout be managed?
14. Which completion verifiers and LLM judges are needed, what evidence may each see, and how will false-positive and false-negative rates be calibrated? **Answered by [ADR-0016](adr/0016-judge-panel-and-verifier-audit-protocol.md) (accepted 2026-07-13);** per-benchmark calibration measurements remain to be produced.
15. What trace and artifact representation best supports replay, diagnosis, redaction, and cross-harness comparison? **Answered by [ADR-0004](adr/0004-trace-storage.md) (accepted 2026-07-13);** first-bridge conformance pending.
16. How should the two reference auto-research frameworks be adapted rather than copied blindly? **Answered by [ADR-0015](adr/0015-auto-research-loop-architecture.md) (accepted 2026-07-13).**
17. Which executor and judge models are approved, with which exact API identifiers, snapshots, settings, and data policies? **Answered at the selection level by [ADR-0017](adr/0017-model-and-infrastructure-pins.md) (accepted 2026-07-13):** MiniMax-M3 executor via OpenCode Go; judges/Analyst as Codex-spawned sub-agents on GPT-5.6 Sol Ultra; exact identifiers/snapshots recorded per campaign at bring-up.
18. Which infrastructure will host browser workers, artifacts, model endpoints, and hidden evaluation? **Answered at the selection level by [ADR-0017](adr/0017-model-and-infrastructure-pins.md) item 7:** one dedicated Linux host, environments via Docker Compose, two-user confinement (conductor/store owner vs. optimizer restricted to its worktree components), holdout inside the owner-only trusted store.
19. What detailed policy is required before permitted live-site testing?
20. Should the repository remain public, and which license should it use?
21. Which implementation language, runtime, package manager, and CI structure should be adopted after the first baseline is selected?
22. Which strong reference model and harness will calibrate Batch 1 against ADR-0012's 35–70% task-level band?
23. How many trials and what uncertainty rule are required near the 35% and 70% boundaries?
24. Which of the 140 Batch 1 candidates survive environment, verifier, duplication, and task-level difficulty audits?
