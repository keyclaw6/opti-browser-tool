# Normalized task catalog

`tasks.jsonl` is the canonical active machine-readable catalog for all **140 provisional candidates**. The runner resolves suite IDs through this file.

## Views of the same task records

- `tasks.jsonl`: canonical normalized catalog, one compact JSON record per line.
- `by-id/<source>/<task-id>.json`: one pretty-printed record per task for direct inspection. These files are generated from `tasks.jsonl` and must match it exactly.
- `task-index.json`: all normalized records keyed by task ID.
- `by-source/*.jsonl`: source-specific partitions.
- `tasks.csv`: flattened review view of key fields.

Every normalized task contains the exact raw candidate record under `provenance.raw_candidate_record`. The normalized fields correct two defects in the superseded 100-task draft:

1. `goal` is populated from the candidate's actual `task_intent` rather than a placeholder.
2. `state_change_expected` is derived from `mutates_state` rather than defaulting to false.

The published reference percentage is explicitly stored as benchmark-family evidence. `per_task_success_percent` remains `null` until local repeated calibration is complete.

The full boundary between included task records and non-vendored upstream runtime assets is documented in `docs/TASK_DATA_GUIDE.md`.


## Are the actual tasks here?

Yes, the catalog contains each candidate's textual goal and exact upstream identity. Every normalized record also embeds the full raw candidate record. It does not contain every upstream binary or dynamic input required to replay the task. In particular, visual-task images, WARC files, ServiceNow state, website containers, and native verifier implementations remain external.

See `docs/TASK_DATA_GUIDE.md` for the source-by-source completeness matrix.

## Resolution order

- Use `tasks.jsonl` as the sequential runner catalog.
- Use `task-index.json` for direct lookup by ID.
- Use `by-source/*.jsonl` when implementing one benchmark bridge.
- Treat `evals/suites/*.json` as ID manifests; they do not duplicate task bodies.
