# Runnable evaluation suite v0

Status: **Provisional and runnable at the orchestration layer**

This release materializes all 140 exact candidates into a backend-neutral evaluation package. It does not claim that any task is finally admitted: per-task success calibration, environment reset checks, known-good completion, and adversarial verifier tests remain pending.

## Accepted difficulty rule

The benchmark-family reference used to source a candidate must lie between **35% and 70%, inclusive**. Benchmark-level scores are not task-level scores. Every task keeps `per_task_success_percent: null` until repeated local calibration under a pinned strong reference protocol.

## Active composition

| Source | Candidate / active primary tasks | Smoke / provisional regression |
|---|---:|---:|
| REAL v1 | 30 | 5 |
| WebArena-Verified | 30 | 5 |
| WorkArena++ Level 2 | 30 | 4 |
| VisualWebArena | 30 | 3 |
| WARC-Bench | 20 | 3 |
| **Total** | **140** | **20** |

`primary.json` currently aliases the unfiltered 140-task candidate pool under ADR-0014. The target final primary suite remains approximately 100 tasks after task-level validation and filtering.

## Why bridge contracts are used

The project has not selected a browser-control substrate. Hardwiring the suite to Playwright, BrowserGym, Selenium, CDP, native pointer input, or another executor would silently decide an open research question.

Each source therefore uses a bridge that must:

1. resolve the pinned upstream task;
2. establish and verify the initial state;
3. run the selected agent harness;
4. invoke the native or independently audited verifier;
5. distinguish agent failure from environment, account, reset, and verifier failure; and
6. emit the common result contract.

This keeps task identity and scoring comparable across visual-first, CLI, and hybrid lanes.

## Fail-closed behavior

Missing adapters, disabled source bridges, reset failures, unavailable accounts, malformed verifier output, and crashed environments produce `invalid` or `error`. Such outcomes invalidate the run for benchmark comparison; they are not ordinary task failures.

## Commands

```bash
pip install -e ./eval_harness
opti-eval validate
opti-eval run --suite smoke --adapter fixture --output runs/smoke-fixture
opti-eval run --suite primary --adapter registry --config evals/config.local.json --output runs/all-140-real
```

Fixture runs test orchestration only and are never reportable benchmark results.

## Remaining admission work

1. Install and pin every upstream benchmark environment.
2. Implement and audit one bridge per source.
3. Run upstream oracles or known-good traces to verify solvability and evaluator behavior.
4. Test near misses, harmful extra actions, premature completion, and evaluator shortcuts.
5. Repeatedly run a pinned strong reference harness to estimate task-level success.
6. Keep tasks in the accepted 35–70% band and record a reason for every exclusion or exception.
7. Filter the 140-task pool into the final approximately 100-task primary suite.
