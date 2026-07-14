# Auto-research implementation ledger

Status: active coordinator ledger. The accepted project mission is to build a
browser-harness research factory whose accepted changes are real, attributable,
repeatable, cumulative, and safe. Passing fixture plumbing is not progress
toward that mission unless the same trust boundary can reject forged, missing,
stale, or statistically lucky evidence.

This ledger consolidates the three independent audits in
`docs/review-reports/`. Work is intentionally sequential: one implementation
package is active at a time, an independent reviewer must return no actionable
findings, and only then may the package be committed and the next package start.

## Operating rules

1. The coordinator owns scope, ordering, audit mapping, and sign-off.
2. An implementation agent owns code and tests for one package only.
3. A separate review agent examines the resulting diff, tests the acceptance
   criteria, and reports findings without editing it.
4. Review findings return to the same implementation agent. Review repeats
   until clean.
5. Every agent must index the current repository with codebase-memory-mcp and
   use graph search/impact traces before editing or reviewing. Direct file reads
   and `rg` remain required for exact contracts and verification.
6. No real or live campaign is authorized by completing scaffold work. The
   pre-activation requirements in `PROGRAM.md` remain binding.

## Dependency-ordered implementation queue

| ID | Status | Package | Audit findings consolidated | Completion boundary |
|---|---|---|---|---|
| AR-001 | complete (`eb25f62`) | Fail external bridge results closed | FOUND-001; CONV-001; OPS-004 | Command/registry output cannot become benchmark-reportable by omission or a minimal pass payload; explicit task identity is mandatory; negative tests prove no state advance. |
| AR-002 | active | Canonical experiment manifest contract | CONV-005 | JSON Schema, runtime validator, example, and conductor-owned attribution agree on one format and one invalid corpus. |
| AR-003 | queued | Required trace/artifact evidence bundle | FOUND-002; CONV-001; OPS-004 | One shared validator rejects missing, malformed, mixed-run, duplicate, out-of-order, identity-mismatched, or unsafe trace/artifact evidence and accepts a conforming positive control. |
| AR-004 | queued | Symmetric run integrity and complete run identity | CONV-002; CONV-009; OPS-012 | Baseline, treatment, smoke, targeted, regression, full, and noise inputs use the same integrity policy; identity binds resolved content, code, environment, verifier, browser, model, and accepted base. |
| AR-005 | queued | Candidate activation and executed-tree binding | CONV-001; OPS-003 | Treatment runs use an immutable materialization of the accepted candidate commit, reject ignored/untracked payloads, and prove candidate/component activation in the trace. |
| AR-006 | queued | Exact causal commit and component-diff enforcement | CONV-007; CONV-008; OPS-001 | Exactly one non-merge, non-empty child commit is accepted; safe in-component delete/rename works; trusted cluster/task/evidence references are conductor-resolved. |
| AR-007 | queued | Trusted Git import boundary | OPS-001 | Optimizer cannot mutate common Git administration; conductor imports and validates a standalone patch/bundle into owner-controlled Git. |
| AR-008 | queued | Candidate sandbox and hard live-site deny | OPS-002; OPS-005 | Candidate runs under a distinct constrained boundary with allowlisted environment/mounts/network/processes; live/destructive transport is denied until ADR-0006 authorization exists. |
| AR-009 | queued | Verifier bundle identity, admission, and revocation | FOUND-007; CONV-004 | Admission binds executable, dependencies, command, environment, task config, and version; any repair/change revokes it; six probes must pass before reuse. |
| AR-010 | queued | Safe store namespace, permissions, and locks | FOUND-008; OPS-007; OPS-008 | Safe campaign IDs, no-follow containment, owner-only modes, per-campaign mutation locks, and per-environment leases prevent escape and races. |
| AR-011 | queued | Journaled exactly-once iteration recovery | OPS-006 | A durable iteration UUID/journal/receipt and ref CAS recover every start/gate/accept failpoint to exactly one committed or aborted result without split brain. |
| AR-012 | queued | Preventative lifecycle driver and operator health | OPS-009; OPS-010; OPS-013 | A persisted driver resumes safely, honors running/paused/stopped plus budgets/deadlines, cleans descendants, and `status` diagnoses reconciliation failures without exposing secrets. |
| AR-013 | queued | Identity-bound transfer and failed-transfer pause | CONV-013; OPS-011 | Finite complete paired transfer evidence is bound to campaign/base/candidate/task/model/environment identities; rejection atomically pauses further starts. |
| AR-014 | queued | Inconclusive outcomes and indivisible attribution | CONV-006; CONV-015 | Infrastructure invalidity is behaviorally inert and does not consume attempts; partial candidates never advance wholesale. |
| AR-015 | queued | Repeated paired statistical acceptance | FOUND-006; CONV-003 | Prespecified paired/interleaved repeats, uncertainty, minimum effect, and campaign-level false-acceptance control reject a stochastic no-op and detect powered positive controls. |
| AR-016 | queued | Durable regression and champion protection | CONV-010 | Repeatedly supported capabilities remain protected across transient misses, and cumulative degradation from the declared champion cannot random-walk through local noise. |
| AR-017 | queued | Event-addressable Analyst, clusters, and learnings | CONV-011 | Benchmark campaigns reject the stub; clusters are trace-backed and trusted; completed causal learnings are required before the next packet. |
| AR-018 | queued | Judge trust identity and quarantine routing | CONV-012 | T2 trust is scoped to exact prompt/model/provider/settings/evidence/corpus identity; only trusted judgments may route; untrusted outputs are state-inert. |
| AR-019 | queued | Source-aware scheduling and auditable task dispositions | FOUND-008; FOUND-010 | Per-source concurrency/leases are enforced; every provisional task has one validated disposition; smoke/source/site/mechanism coverage is mechanically checked. |
| AR-020 | queued | Generated commands, status prose, and decision metadata | FOUND-009; FOUND-012; CONV-016; OPS-014 | Packets invoke the real workflow; accepted-contract versus activation-pending text matches the decision register; executable documentation tests prevent drift. |

## Required work deferred by real dependencies

These are not rejected. Implementing pretend versions would make the factory
less trustworthy, so they start only when their dependency is real.

| ID | State | Work | Why deferred / activation condition |
|---|---|---|---|
| EXT-001 | blocked-external | Pin, deploy, reset, and bridge all five benchmark sources | FOUND-003. Requires upstream runtime assets, credentials/access, native verifiers, and observable reset state. Start source-by-source when an environment is actually available. |
| EXT-002 | decision-required | Select the first browser baseline and build the minimal seed | FOUND-005 and ADR-0003. Complete Phase-1 harness research and obtain the owner's explicit backend decision before implementation. |
| EXT-003 | blocked-external | Create a private disjoint holdout | FOUND-004; CONV-013. Requires a genuinely private source and owner-controlled commitment; moving public tasks is not a holdout. |
| EXT-004 | blocked-by-EXT-001/002 | Calibrate all 140, filter/freeze suites, and source Batch 2 | FOUND-006/010. Requires real resets, admitted verifiers, a reference protocol, and the exact cheap-executor seed. |
| EXT-005 | blocked-by-real-traces | Calibrate real Analyst/T2 roles | CONV-011/012. Code identity/routing comes first; statistical trust requires held-back real trace corpora. |
| EXT-006 | blocked-by-real-smoke | Measure capacity, cost, retention, and exact-seed noise | FOUND-011. Values must come from five-source smoke and frozen iteration identity, not constants invented in code. |

## Deliberately not implementing now

- A general compound/multi-component acceptance exception (CONV-014). The
  one-component causal rule protects attribution. Add only a bounded staged
  mechanism if real experiments demonstrate a specific irreducible dependency.
- Automatic regression promotion. Keep promotion owner-controlled until real
  verifier, flake, and repeat evidence establishes safe thresholds.
- A distributed transaction system, database platform, broad observability
  stack, or cloud scheduler. The accepted scope is a single-host factory; a
  small journal, filesystem locks, receipts, and direct health checks suffice.
- Live-site authorization machinery beyond the hard deny in AR-008. ADR-0006
  remains open, so the only correct current behavior is prevention.

## Completion definition

The code-only queue is complete when AR-001 through AR-020 have independent
review sign-off and the full repository verification is green. That still does
not authorize auto-research. Activation additionally requires the EXT work,
the real injection/fault rehearsal, and the project owner's explicit start.
