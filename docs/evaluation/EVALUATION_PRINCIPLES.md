# Evaluation Principles

## Status

Draft principles derived from the project charter. The provisional 140-task candidate pool, nested 20-task smoke set, and 35–70% calibration band are recorded, but the final suite composition, repeat counts, judge models, holdout, and experiment gates remain open.

## Unit of evaluation

A run is a versioned tuple of task, task environment, lane, harness revision, executor model and settings, browser backend and version, observation policy, action policy, seed or replicate identifier, and verifier version.

## Task sets

- **Smoke:** fast and deterministic; detects implementation breakage.
- **Development/main:** visible tasks selected for difficult interaction and varied failure modes.
- **Regression:** previously fixed failures and critical invariants.
- **Hidden holdout:** unavailable to the optimizing agent.
- **Live-site:** separately reported, opt-in, and repeated where instability warrants it.

## Objective measurements

Success, verifier output, final browser state, elapsed time, tokens, model cost, tool calls, browser actions, retries, failed actions, context size, and infrastructure incidents are computed directly.

## Judge outputs

Judges return evidence references, confidence, structured labels, and a concise rationale. They do not merely emit an unconstrained score. The trace/root-cause judge identifies the earliest meaningful divergence, not only the final visible error.

Judges should be independent where practical. Baseline/treatment labels should be blinded for subjective process comparison. The adjudicator receives disagreements and additional evidence; it does not average incompatible judgments.

## Counterfactual diagnosis

Counterfactual reruns may supply a correct element, plan step, recovered session, dismissed popup, or working action mechanism. These runs diagnose capability boundaries and are never counted as ordinary task success.

## Dynamic tasks

Measure baseline variance before choosing repetition counts and acceptance thresholds. Record page version, locale, viewport, account state, browser version, and time window so environmental drift can be distinguished from harness changes.

## Anti-overfitting

Do not expose hidden verifier logic or holdout traces. Promote fixed failures into regression coverage. Rotate visible discovery tasks or task variants. Evaluate transfer by failure class, site family, and unseen layout—not only by exact task ID.
