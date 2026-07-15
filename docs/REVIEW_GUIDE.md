# Independent review guide

This guide is for an agent reviewing whether the project state, decisions, and evaluation artifacts are internally sound.

## 1. Establish the evidence hierarchy

1. Read the project charter.
2. Read the decision process and decision register.
3. Treat only Accepted ADRs as binding.
4. Treat open/proposed ADRs as questions or candidate directions.
5. Treat superseded ADRs and `archive/superseded/` as historical evidence only.
6. Verify claims about task counts and contents against machine-readable files, not prose alone.

## 2. Review every accepted decision

For each accepted ADR, check:

- the owner approval is explicit;
- context and rationale match the project objective;
- rejected or deferred alternatives are visible;
- consequences and required validation are stated;
- later documents do not silently contradict it; and
- any later change uses a superseding ADR.

Current accepted ADRs are 0001, 0004, 0005, 0007, 0012, 0014, 0015, 0016, and 0017.

## 3. Check non-decisions

Confirm that the repository does not falsely claim selection of:

- browser engine or automation library;
- visual-first, CLI, or hybrid foundation;
- detailed live-site policy;
- trial counts near the band boundaries; or
- final approximately 100-task suite.

(Models, judges, and the reference harness are now selected by ADR-0017; judge PROMPTS remain uncalibrated and untrusted until measured.)

Implemented bridge and fixture code is provisional infrastructure, not evidence that any of those choices is accepted.

## 4. Verify task preservation

Run:

```bash
python scripts/verify_documentation.py --repo-root .
python scripts/validate_json_schemas.py --repo-root .
python scripts/verify_repository_completeness.py --repo-root .
python scripts/verify_file_manifest.py --repo-root .
```

Then independently confirm:

- 140 raw candidate records;
- 140 normalized catalog records;
- 140 individual by-ID JSON files;
- identical task-ID sets across those views;
- source counts of 30 REAL, 30 WebArena-Verified, 30 WorkArena L2, 30 VisualWebArena, and 20 WARC-Bench;
- 140 IDs in both provisional primary and candidate-pool manifests;
- 20 smoke and 20 provisional regression IDs nested in primary;
- normalized goals equal raw task intents where a fixed intent is available;
- per-task success remains unset; and
- benchmark aggregates are labeled as source-family evidence only.

## 5. Verify runnable orchestration without misreading it

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ./eval_harness
opti-eval validate
opti-eval run --suite smoke --adapter fixture --output runs/review-smoke
```

The fixture run proves only catalog, scheduling, result, and artifact plumbing. It is not browser evaluation and must report `benchmark_reportable=false`.

## 6. Inspect known limitations

A sound review should explicitly note that:

- real source bridges are absent;
- external benchmark assets are not vendored;
- task-level calibration and verifier audits are pending;
- WorkArena runtime instructions are generated from task class and seed;
- the regression seed is provisional; and
- the final suite remains unfrozen.

## 7. Produce a review record

A review should conclude with one of:

- confirmed as internally consistent;
- confirmed with nonblocking documentation corrections;
- blocked by missing or contradictory evidence; or
- invalid because preservation, task identity, or decision history cannot be reproduced.

Record exact file paths, commands, commit, and observed counts. Do not approve a technical direction merely because runnable scaffolding already exists.

## 8. Rebuild a preservation archive

After the repository is clean and all manifests are current:

```bash
python scripts/build_repository_archive.py \
  --output ../opti-browser-tool-complete.zip \
  --bundle
```

The builder refuses a dirty worktree, clones committed `HEAD` locally with
`--no-hardlinks`, removes the clone origin, and rejects external Git common
directories or object alternates. It archives the standalone clone with its
self-contained `.git`, tests ZIP integrity, restores stored Unix permissions
during extraction, and requires the extracted checkout to remain clean. It
then runs completeness (including documentation and Git integrity), the file
manifest, and the clean local-wheel install proof with installed tests once on
the extracted archive. ZIP and optional bundle outputs receive SHA-256
sidecars.
