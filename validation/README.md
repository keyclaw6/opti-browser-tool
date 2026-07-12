# Validation artifacts

These files record checks against the reconstructed repository state. They are evidence about preservation, documentation, schemas, and runner plumbing. They are **not** browser-agent benchmark results.

## Core integrity checks

- `documentation-validation.json` — verifies the documentation map, local links, ADR coverage, exact 140-task preservation, by-ID task copies, source counts, suite nesting, accepted 35–70% band, and current planning-YAML status markers.
- `repository-validation.json` — validates the normalized catalog, raw provenance, all 140 by-ID task files, source distribution, and active suite counts.
- `schema-validation.json` — validates 140 normalized tasks, four suite manifests, and stored run summaries against the repository JSON Schemas.
- `completeness-report.json` — fail-closed aggregate check for required files, suite validity, and documentation validity.
- `unit-tests.txt` and `compileall.txt` — runner test and Python syntax results.
- `MANIFEST.sha256` at the repository root — content hashes for repository files outside `.git` and other excluded runtime directories.

## Runner-plumbing checks

- `fixture-140-run.json` and `fixture-140-summary.json` — complete orchestration over all 140 task records using a deterministic synthetic adapter.
- `command-bridge-summary.json` — one-task external command-bridge contract check using the included synthetic bridge.
- `registry-doctor.json` — parsing and source coverage of the disabled example registry.
- `install-check.txt` — prior editable-install and CLI check.

Both the fixture adapter and included fixture command bridge are synthetic. Their summaries must contain:

```json
{
  "benchmark_reportable": false,
  "acceptance_decision_eligible": false
}
```

Their pass/fail counts demonstrate only scheduling and result plumbing. They must never be cited as agent performance or used to accept a harness hypothesis.

## Re-running the checks

From the repository root:

```bash
python scripts/verify_documentation.py --repo-root .
python scripts/validate_json_schemas.py --repo-root .
PYTHONPATH=eval_harness/src python -m opti_eval validate --repo-root . --json
OPTI_BROWSER_REPO_ROOT="$PWD" PYTHONPATH=eval_harness/src \
  python -m unittest discover -s eval_harness/tests -v
python scripts/verify_repository_completeness.py --repo-root .
python scripts/verify_file_manifest.py --repo-root .
```

The schema check has an optional dependency: `python -m pip install jsonschema`. The evaluation runner itself remains standard-library-only.
