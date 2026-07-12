# Repository recovery and completeness manifest

Date: 2026-07-11

## Why reconstruction was necessary

The latest working directory contained only 26 files, had no `.git` directory, and had no executable evaluation-runner source beyond a README. It did contain later ADRs and a partial 100-task catalog. Earlier archives contained the complete repository history and the exact 140-task candidate batch.

## Reconstruction sources

The active repository was rebuilt from:

1. `opti-browser-tool-task-candidates-batch-1.zip` — complete Git repository through commit `5cb8e7f`, including all prior planning, benchmark research, and 140 exact candidate records;
2. the later partial `/mnt/data/opti-browser-tool/` folder — ADR-0012, ADR-0013, the incomplete 100-task suite draft, and related documentation; and
3. newly implemented runner code and validation files required to make the suite genuinely runnable at the orchestration layer.

The incomplete 100-task draft is preserved verbatim under `archive/superseded/runnable-suite-v0-100/`.

## Active recovered contents

- complete prior Git history and configured GitHub origin;
- charter, roadmap, documentation map, agent handoff, independent review guide, decision process, open questions, references, architecture, safety, models, and evaluation planning;
- ADR-0001 through ADR-0014 with supersession history;
- benchmark-source report and comparison matrix;
- all 140 raw candidate records in CSV and JSONL;
- candidate index, source lock, source audit, summaries, calibration plan, licenses, and validation/render scripts;
- normalized active catalog of all 140 tasks, including actual task goals, correct state-change flags, and one generated JSON file per task;
- source-specific catalog partitions and a keyed task index;
- 140-task candidate/primary manifests, 20-task smoke, and provisional regression manifests;
- an installable standard-library-only `opti-eval` package;
- fixture, command, and source-registry adapters;
- fail-closed result handling and run summaries;
- schemas, examples, unit tests, Make targets, and durable validation reports; and
- a documentation map, agent handoff, task-data guide, independent review guide, and a file checksum manifest.

## Evidence boundary

The archive contains the actual text instructions and full normalized records for all 140 tasks, not merely a prose description of them. The authoritative locations are `research/benchmarks/task-candidates/batch-1-candidates.jsonl` and `evals/catalog/tasks.jsonl`; see `docs/TASK_DATA_GUIDE.md`.

It does not vendor all benchmark websites, data snapshots, visual goal images, WACZ archives, ServiceNow instances, accounts, credentials, or native verifier implementations. Real browser execution still requires pinned upstream environments and audited source bridges. No task has yet received a locally measured task-level success rate.

## Completeness checks

The repository is accepted as reconstructable only if all of the following pass:

- 140 raw candidates, 140 normalized catalog rows, and 140 individual by-ID task files with identical IDs;
- source counts of 30/30/30/30/20;
- active primary and candidate-pool manifests containing all 140 tasks;
- 20 smoke and 20 provisional regression tasks nested inside primary;
- every source-family reference inside the accepted 35–70% band;
- every normalized goal equal to the raw `task_intent`;
- every normalized state-change flag equal to raw `mutates_state`;
- package editable installation;
- unit tests;
- a complete 140-task fixture run;
- external command-bridge execution;
- `git fsck --full`; and
- final ZIP integrity plus clean extraction and rerun of validation from the extracted copy.

## Rebuilding the complete archive

Use `scripts/build_repository_archive.py` from a clean repository. It includes `.git`, verifies the source tree, extracts the ZIP into a temporary directory, reruns repository and documentation checks, and writes SHA-256 sidecars.
