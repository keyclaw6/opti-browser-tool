# Auto-research hardening handout

Date: 2026-07-15
Branch: `codex/auto-research-hardening`
Base at start of this work: `6cad1f0` (`origin/main`, `main`)

## Why this branch exists

The project mission is to build an auto-research factory for a browser-agent
harness: run controlled browser-harness experiments, diagnose failures from
trusted traces, propose small component changes, gate them with attributable
evidence, and converge on improved performance without accepting forged,
stale, lucky, or fixture-only results.

Three independent audits were gathered and consolidated into
`docs/AUTO_RESEARCH_IMPLEMENTATION_LEDGER.md`. The ledger is the coordinator
source of truth for the hardening program. It intentionally proceeds one
package at a time with an implementer/reviewer loop.

## Git history created in this chat

The branch currently has these chat-created commits after `main`:

1. `2fffe08 docs: add foundations audit report`
   - Added the first review report under `docs/review-reports/`.
2. `7995f06 docs: add convergence audit report`
   - Added the second review report under `docs/review-reports/`.
3. `420925b docs: add operations audit report`
   - Added the third review report under `docs/review-reports/`.
4. `1f888ae docs: establish audit implementation program`
   - Added the consolidated implementation ledger and sequencing strategy.
5. `eb25f62 fix: fail external bridge evidence closed`
   - Completed AR-001.
   - External command/registry evidence now fails closed instead of becoming
     benchmark-reportable from a minimal or identity-free payload.
6. `0867538 docs: advance auto-research ledger to AR-002`
   - Marked AR-001 complete and advanced the ledger.
7. `f21038c fix: unify experiment manifest contract`
   - Completed AR-002.
   - Runtime validator, JSON Schema, examples, and conductor attribution now
     share the same manifest contract.
8. `90e6281 docs: advance auto-research ledger to AR-003`
   - Marked AR-002 complete and made AR-003 active.

The current dirty worktree is AR-003 implementation work and this handout. It
is being committed as a handoff snapshot, not as final AR-003 sign-off.

## Current AR-003 state

AR-003 is "Required trace/artifact evidence bundle". Its target completion
boundary is:

> One shared validator rejects missing, malformed, mixed-run, duplicate,
> out-of-order, identity-mismatched, or unsafe trace/artifact evidence and
> accepts a conforming positive control.

The uncommitted AR-003 work already touches the eval, judge, loop, schema,
test, and documentation surfaces. The core direction is:

- runner-owned task manifests and stricter result/task/source identity;
- strict persisted JSON/JSONL readers across catalogs, suites, bridge output,
  summaries, traces, admissions, and quarantine state;
- evidence validation for ordered trace events, final verifier events, final
  visible browser state, artifact visibility, artifact hashing, containment,
  symlink avoidance, and run/task identity;
- stricter T1 task expectation parsing and comparison;
- exact-run quarantine behavior keyed by `task_id` plus `run_ref`;
- schema and corpus coverage for finite JSON, duplicate keys, unsafe numbers,
  Unicode edge whitespace, LF-only JSONL framing, and malformed evidence.

Important deferrals are still intentional:

- AR-004 owns symmetric/full run identity.
- AR-005 owns candidate activation and executed-tree binding.
- AR-008 through AR-011 and AR-020 remain later packages.
- Real benchmark bridges and source environments remain external/deferred.
- No live auto-research campaign is authorized by this branch.

## Last known verification

The replacement AR-003 implementation agent reported no additional edits and
these checks passing:

- focused adversarial matrix: 64 passed, one optional `jsonschema` skip;
- eval harness tests: 28 passed;
- judge harness tests: 27 passed;
- loop harness tests: 74 passed with normal Python, one optional skip;
- loop harness tests via `uv run --with jsonschema`: 74 passed, zero skips;
- schema audit via `uv run --with jsonschema python scripts/validate_json_schemas.py --repo-root .`;
- catalog validation: 140 candidates, primary 140, smoke 20, regression 20;
- docs verification: 82 Markdown files, 161 local links, 17 ADRs;
- archive/repository completeness checks;
- `compileall`;
- `git diff --check`;
- AR-003 production/test Ruff subset.

The full repository Ruff run still has 11 pre-existing E702 findings in old
tests (`test_judges.py` and `test_units.py`) that predate this branch. They
were intentionally not cleaned up as part of AR-003.

`python scripts/verify_file_manifest.py --repo-root .` was expected to fail
before AR-003 finalization because `FILE_INVENTORY.tsv` and `MANIFEST.sha256`
were not regenerated. The last reported failure was 39 checksum mismatches.

## Why this is a handoff snapshot

The final independent AR-003 reviewer was still running when the user asked to
stop and create a handoff. That reviewer was interrupted so the worktree would
not keep changing during this handoff.

This snapshot should therefore be treated as a strong AR-003 candidate, not an
approved AR-003 completion commit. The next agent should independently review
the committed diff before marking AR-003 complete in the ledger.

## How the next agent should resume

1. Read `AGENTS.md`, `docs/AGENT_HANDOFF.md`, and
   `docs/AUTO_RESEARCH_IMPLEMENTATION_LEDGER.md`.
2. Index the current repository with codebase-memory-mcp before reviewing or
   editing.
3. Review only AR-003 first. Do not start AR-004 until AR-003 is clean.
4. Re-run the focused adversarial checks around:
   - strict JSON and LF-only JSONL parsing;
   - duplicate key, NaN/Inf, and overflow rejection;
   - trace ordering and final verifier-event semantics;
   - artifact containment, symlink, hash, and visibility behavior;
   - exact-run quarantine blocking and favorable/adverse disposition behavior;
   - schema loader finite-domain behavior before `jsonschema`.
5. If the review finds issues, fix AR-003 only and repeat the review loop.
6. Once AR-003 is clean, regenerate `FILE_INVENTORY.tsv` and `MANIFEST.sha256`
   with `make manifest-build`, run the full relevant verification suite, then
   make a final AR-003 completion commit.
7. Only then update the ledger to mark AR-003 complete and activate AR-004.

## Files to pay special attention to

- `eval_harness/src/opti_eval/models.py`
- `eval_harness/src/opti_eval/summary.py`
- `eval_harness/src/opti_eval/runner.py`
- `eval_harness/src/opti_eval/catalog.py`
- `eval_harness/src/opti_eval/util.py`
- `eval_harness/src/opti_eval/adapters/command.py`
- `judge_harness/src/opti_judge/evidence.py`
- `judge_harness/src/opti_judge/quarantine.py`
- `judge_harness/src/opti_judge/t1_checks.py`
- `loop_harness/src/opti_loop/eligibility.py`
- `loop_harness/src/opti_loop/conductor.py`
- `loop_harness/src/opti_loop/gates.py`
- `schemas/result.schema.json`
- `schemas/trace-event.schema.json`
- `evals/schemas/*.schema.json`
- `scripts/validate_json_schemas.py`
- `scripts/evidence_contract_corpus.py`
- `eval_harness/tests/test_evidence_contract_corpus.py`
- `judge_harness/tests/test_quarantine_state.py`
- `loop_harness/tests/test_evidence_eligibility.py`

## Local generated artifacts

The local `.codebase-memory/` directory is a generated index artifact and
should not be committed. The last useful reported index name from the
implementation agent was `opti_browser_tool_ar003_impl_resume`, but a new agent
should build a fresh index against this committed state.
