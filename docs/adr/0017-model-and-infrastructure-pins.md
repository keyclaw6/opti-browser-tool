# ADR-0017: Model and infrastructure pins for loop bring-up

- Status: Accepted
- Date opened: 2026-07-13
- Date proposed: 2026-07-13
- Date accepted: 2026-07-13
- Source: explicit project-owner direction (project thread, 2026-07-13); items 4–7 delegated by the owner and decided by the agent
- Answers: Open Question 17 at the selection level (exact API identifiers/snapshots are recorded per campaign at bring-up)
- Nonbinding transition proposal: [ADR-0018](0018-auto-research-readiness-protocol-transition.md) would replace item 7's literal writable path with a frozen campaign harness-build allowlist while preserving two-user confinement; it has no effect unless explicitly accepted.

## Decision

1. **Loop executor (harness-under-test model): MiniMax-M3**, accessed through the owner's **OpenCode Go subscription**. The executor stays fixed within experiments (ADR-0001); the exact API identifier, snapshot/revision, and sampling settings are recorded in campaign configuration at bring-up — the run-identity binding (ADR-0005/noise band) already requires them.
2. **Judge panel (T2) and the Analyst: sub-agents spawned by the owner's Codex harness, model preset GPT-5.6 Sol Ultra.** Judges are exempt from the executor cost economy (ADR-0016). Wiring uses opti-judge's `command` model provider; judge prompts and the preset are versioned like verifiers (ADR-0016 calibration rule 4). Calibration-before-trust is unchanged: the pin does not make any judge trusted.
3. **Research and exploration tasks** (browser-harness landscape review, the optional explore/seed pass): **GPT-4 Pro via OpenCode Go** *(owner's stated name via voice transcription; verify the exact product identifier when wiring)*.
4. **Calibration reference harness** (owner approved the direction; specifics delegated): **BrowserGym GenericAgent with GPT-5.6 Sol Ultra** as the frontier reference model — the most reproducible pinned stack, and the denomination of the repo's own benchmark sourcing evidence. A second, architecturally different reference on a subset (de-biasing the yardstick) remains optional at calibration time.
5. **Transfer checkpoint panel** (delegated): **GPT-5.6 Sol Ultra + GPT-4 Pro** — both reachable through existing subscriptions. The panel is run configuration recorded per checkpoint; revising it does not reopen this ADR.
6. **Hidden-holdout home** (owner delegated the choice to automation): selected by the **conductor-side** setup automation at first campaign bring-up, **before iteration 1**, defaulting to `<store-root>/holdout/` inside the owner-only trusted store. Per the constitution and ADR-0015, the **optimizer never chooses, sees, or learns this location** — the owner's delegation is executed on the conductor side precisely so the holdout invariant survives it.
7. **Compute home** (delegated): a single dedicated Linux host (the owner's machine or a rented server) running (a) the five benchmark environments via Docker Compose, (b) the conductor and trusted store under an owner-only OS user, and (c) the optimizer (Codex/OpenCode) as a **separate OS user whose writable surface is only its campaign worktree's `harness/components/`** — the ADR-0015 deployment-confinement requirement. Credentials flow through the repository's dotenvx workflow; subscription auth is preferred over per-call API keys, matching the owner's standing practice.

## Consequences

Model comparisons are separate experiments (ADR-0001): changing the executor or a judge preset changes the run identity and invalidates cross-comparison with prior runs; the noise band must be re-measured. The judge preset being stronger than the executor is deliberate — a cheap executor with a blind gate corrupts every downstream decision (ADR-0016 economics).

## Validation and revisit triggers

Exact identifiers/snapshots are validated at bring-up (first admission runs and the ADR-0005 injection catalog exercise the full pinned stack). Revisit only if the selection policy itself changes (for example abandoning the fixed-cheap-executor bet after a failed transfer checkpoint, per the pre-registered criterion); routine snapshot bumps are recorded in campaign config and the ledger, not by superseding this ADR.
