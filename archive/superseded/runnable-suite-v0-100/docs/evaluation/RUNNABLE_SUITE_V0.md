# Runnable evaluation suite v0

Status: **Provisional and runnable**

This release materializes exact candidates into a benchmark-agnostic evaluation package. It does not claim that the tasks are fully admitted: per-task success calibration, environment reset checks, oracle completion, and verifier adversarial tests remain pending.

## Accepted difficulty rule

The benchmark-family reference result used to source a candidate must be between **35% and 70%, inclusive**. This replaces the incorrectly recorded 40% floor. Benchmark-level scores are not treated as per-task scores.

## Suite composition

| Source | Primary | Smoke / provisional regression seed | Reference result |
|---|---:|---:|---:|
| REAL v1 | 25 | 5 | 41.0% |
| WebArena-Verified | 25 | 5 | 53.7% |
| WorkArena++ Level 2 | 20 | 4 | 69.4% |
| VisualWebArena | 15 | 3 | 58.3% |
| WARC-Bench | 15 | 3 | 64.8% |
| **Total** | **100** | **20** | — |

The smoke suite and provisional regression seed contain the same 20 tasks in v0. They are strict subsets of the 100-task primary suite. The permanent regression suite will later grow from repeatedly verified fixes.

## Why a bridge contract instead of a hardwired browser stack

The project has not yet selected its first browser backend or agent architecture. Hardwiring this suite to Playwright, BrowserGym, or another executor would silently decide that open research question. Instead, each benchmark source is integrated through a small bridge that resolves the upstream task, resets the environment, runs the chosen harness, invokes the native verifier, and emits one standardized result.

This preserves comparability across visual-first, CLI, and hybrid lanes while allowing the exact same task IDs and result schema to be used by each lane.

## Fail-closed behavior

A missing adapter, reset failure, unavailable account, malformed verifier output, or crashed environment produces an `invalid` or `error` result. It does not count as an ordinary agent failure and it invalidates the experiment for acceptance decisions.

## Commands

```bash
pip install -e ./eval_harness
opti-eval validate
opti-eval run --suite smoke --adapter fixture --output runs/smoke-fixture
opti-eval run --suite primary --adapter registry --config evals/config.local.json --output runs/primary
```

The fixture adapter tests orchestration only and must never be reported as a benchmark result.

## Remaining admission work

1. Install and pin every upstream benchmark environment.
2. Implement and audit one bridge per source.
3. Run upstream oracle or known-good traces to verify solvability and verifier correctness.
4. Repeatedly run a pinned strong reference harness to estimate each task’s success rate.
5. Retain tasks whose measured reference success lies within 35–70%; replace those outside the band.
6. Freeze the verified suite and its checksums only after the above gates pass.
