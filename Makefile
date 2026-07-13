PYTHON ?= python
REPO_ROOT := $(CURDIR)
PYTHONPATH := $(REPO_ROOT)/eval_harness/src

.PHONY: eval-build eval-validate eval-test eval-smoke-fixture eval-all-fixture docs-verify schema-verify manifest-build archive-build archive-verify loop-test loop-init-dryrun judge-test

LOOP_PYTHONPATH := $(REPO_ROOT)/eval_harness/src:$(REPO_ROOT)/loop_harness/src
JUDGE_PYTHONPATH := $(LOOP_PYTHONPATH):$(REPO_ROOT)/judge_harness/src

eval-build:
	$(PYTHON) scripts/build_eval_catalog.py

eval-validate:
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m opti_eval validate --repo-root $(REPO_ROOT)

eval-test:
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s eval_harness/tests -v

eval-smoke-fixture:
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m opti_eval run --suite smoke --adapter fixture --fixture-pass-rate 0.55 --output runs/smoke-fixture --overwrite

eval-all-fixture:
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m opti_eval run --suite primary --adapter fixture --fixture-pass-rate 0.55 --max-workers 8 --output runs/all-140-fixture --overwrite

loop-test:
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(LOOP_PYTHONPATH) $(PYTHON) -m unittest discover -s loop_harness/tests -v

judge-test:
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(JUDGE_PYTHONPATH) $(PYTHON) -m unittest discover -s judge_harness/tests -v

loop-init-dryrun:
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(LOOP_PYTHONPATH) $(PYTHON) -m opti_loop init --campaign dryrun --adapter fixture
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(LOOP_PYTHONPATH) $(PYTHON) -m opti_loop measure-noise --campaign dryrun
	OPTI_BROWSER_REPO_ROOT=$(REPO_ROOT) PYTHONPATH=$(LOOP_PYTHONPATH) $(PYTHON) -m opti_loop start --campaign dryrun

docs-verify:
	$(PYTHON) scripts/verify_documentation.py --repo-root $(REPO_ROOT)

schema-verify:
	$(PYTHON) scripts/validate_json_schemas.py --repo-root $(REPO_ROOT)

manifest-build:
	$(PYTHON) scripts/build_file_manifest.py

archive-build:
	$(PYTHON) scripts/build_repository_archive.py --output ../opti-browser-tool-complete.zip --bundle

archive-verify:
	$(PYTHON) scripts/verify_repository_completeness.py --repo-root $(REPO_ROOT)
