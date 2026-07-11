# Normalized task catalog

`tasks.jsonl` is the active machine-readable catalog for all **140 provisional candidates**. `tasks.csv` is a flattened review view, `task-index.json` is a keyed copy for simple tooling, and `by-source/` contains source-specific JSONL partitions.

Every task contains the exact raw candidate record under `provenance.raw_candidate_record`. The normalized fields correct two defects in the superseded 100-task draft:

1. `goal` is populated from the candidate's actual `task_intent` rather than a placeholder.
2. `state_change_expected` is derived from `mutates_state` rather than defaulting to false.

The published reference percentage is explicitly stored as benchmark-family evidence. `per_task_success_percent` remains `null` until local repeated calibration is complete.
