PYTHON ?= python
REPO_ROOT := $(CURDIR)
PYTHONPATH := $(REPO_ROOT)/eval_harness/src

.PHONY: eval-build eval-validate eval-test eval-smoke-fixture eval-all-fixture archive-verify

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

archive-verify:
	$(PYTHON) scripts/verify_repository_completeness.py --repo-root $(REPO_ROOT)
