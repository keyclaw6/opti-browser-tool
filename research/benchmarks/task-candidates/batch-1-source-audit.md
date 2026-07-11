# Batch 1 source-manifest audit

- Audit date: 2026-07-11
- Scope: task identity and metadata only
- Result: source identity checks passed for the 140 provisional candidates
- Not tested here: browser launch, login, reset, oracle solvability, evaluator correctness, or task-level success rate

## Checks performed

| Source | Pinned input | Identity check | Result | Limitation |
|---|---|---|---|---|
| REAL | `agisdk 0.3.5`, `REAL/browsergym/webclones/v1/tasks/*.json` | Every selected native ID exists; normalized goal text, difficulty label, and `possible=true` match the candidate row | 30/30 passed | No REAL site or evaluator was executed |
| WorkArena++ L2 | `browsergym-workarena 0.5.3`, `get_all_tasks_agents(filter="l2", meta_seed=42)` | The package generated 235 exact task-class/seed pairs; every selected pair is present | 30/30 passed | This was a metadata-only import. The package's Playwright version guard was bypassed for import because no browser API was invoked. Seeded natural-language goals still require materialization on the pinned ServiceNow instance |
| WebArena-Verified | `webarena-verified 1.2.3`, full verified dataset | Every selected ID exists; normalized intent text and site match | 30/30 passed | Network-trace evaluators and environment resets were not executed |
| VisualWebArena | `libvisualwebarena 0.0.15`, `visualwebarena/test_raw.json` | Every selected ID exists; normalized intent and site match; every row is overall-medium with medium or hard visual difficulty | 30/30 passed | Referenced task images and visual necessity were not audited; screenshot ablation remains required |
| WARC-Bench | commit `98d213ccd2b4380761738e1d144467a8695e37c5`, `src/orby/subtask_benchmark/environments/benchmark.json` | The exact upstream manifest was re-fetched and returned Git blob `6b2bc7ee04b3231325fe3a84b195d26d0c589287`, matching the source lock. Candidate selectors and copied task metadata are internally consistent | 20 selectors retained | WACZ archives were not downloaded or executed in this pass; construction-time known-issue screening must be repeated when the environments are installed |

## Reproduction inputs

The exact selectors are in [`batch-1-selection.json`](batch-1-selection.json). Package versions, source locations, score evidence, and checksums are in [`batch-1-sources.lock.json`](batch-1-sources.lock.json). The canonical candidate rows are in [`batch-1-candidates.jsonl`](batch-1-candidates.jsonl).

The internal artifact validator is:

```bash
python research/benchmarks/scripts/validate_candidate_batch_1.py
```

The source audit is deliberately narrower than task admission. A task remains provisional until its environment, reset, verifier, safety properties, repeated reference-system success rate, and duplication risk are tested.
