# Candidate Task Audit Record

Use one record per candidate task. A task is not admitted merely because its parent benchmark is recommended. Preserve evidence paths so another agent can reproduce the review.

## Review metadata

- Audit status: not started / in progress / passed / failed / quarantined
- Auditor:
- Independent reviewer:
- Audit date:
- Related ADR or issue:
- Evidence directory:

## Identity and provenance

- Internal task ID:
- Benchmark and exact version/commit:
- Upstream task ID:
- Task-definition checksum:
- Environment/site and exact revision or image digest:
- Evaluator revision/checksum:
- Source URL:
- License and terms reviewed:
- Redistribution restrictions:

## Task definition

- User goal:
- Initial state and seed:
- Expected final state:
- Reference completion path:
- Estimated minimum meaningful actions:
- Maximum actions and timeout proposed:
- Is the task state-changing, retrieval, navigation, or mixed?
- Is any final natural-language answer necessary for success?

## Coverage labels

- Workflow class:
- Interaction mechanisms:
- Visual evidence required:
- Forms, filters, settings, editors, or configuration:
- Tabs, frames, dialogs, downloads, uploads, or clipboard:
- Popup, cookie, delay, dynamic-update, infinite-scroll, or stale-state exposure:
- Recovery, replanning, or infeasibility behavior:
- Social / transactional / enterprise classification:
- Safety sensitivity:
- Duplicate-template or interaction-graph cluster:

## Environment and reset audit

- Setup procedure:
- Reset procedure:
- Authentication/session requirements:
- External service dependencies:
- Launch and reset latency:
- Reset trials and success count:
- State leakage across tasks or tabs:
- Known browser-specific behavior:
- Known instability or infrastructure failures:

## Oracle solvability audit

- Oracle/human operator:
- Trials and successes:
- Successful trace paths:
- Alternative valid paths observed:
- Ambiguous instructions or impossible states:
- Required benchmark-private knowledge:
- Oracle conclusion:

## Evaluator audit

- Evaluator type:
- Evidence visible to evaluator:
- Evidence unavailable to executor but available to evaluator:
- Positive fixture: verified true success
- No-op fixture: task untouched
- Partial-completion fixture:
- Wrong-target fixture:
- Plausible-but-false completion claim:
- Correct state with malformed final answer:
- Incorrect state with correct-looking final answer:
- Infrastructure-error fixture:
- Observed false positives:
- Observed false negatives:
- Independent verifier or manual cross-check:
- Evaluator conclusion:

## Shortcut and leakage audit

- Can the task be solved from hidden labels, URLs, DOM metadata, or benchmark files without performing the intended interaction?
- Can an agent trigger the evaluator without reaching the intended state?
- Is the answer or operation code exposed in page source or task artifacts?
- Is the task likely present in public trajectories or training corpora?
- Mitigation or rejection decision:

## Baseline evidence

Record exact model snapshot, harness commit, system prompt, observation format, action interface, memory scope, step budget, retries, evaluator, and date for every run.

### Simple baseline

- Protocol ID:
- Trials / successes:
- Median actions and time:
- Failure classifications:

### Strong reference harness

- Protocol ID:
- Trials / successes:
- Median actions and time:
- Failure classifications:

### Difficulty conclusion

- Estimated success interval:
- Saturated, discriminative, too hard, or invalid:
- Does failure reflect the agent rather than the environment/evaluator?

## Selection outcome

- Decision: primary / smoke+primary / initial regression / replacement pool / hidden-holdout candidate / rejected / quarantined
- Rationale:
- Capability coverage gained:
- Correlated task displaced or avoided:
- Required follow-up:
- Owner approval reference:
