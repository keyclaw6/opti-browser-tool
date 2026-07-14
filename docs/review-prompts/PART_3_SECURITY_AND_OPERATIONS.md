# Review Commission 3 of 3 — Security and Operations

Copy this entire file into a fresh reviewing-agent session.

---

## OPTI BROWSER TOOL — SECURITY, RECOVERY, AND AUTONOMY AUDIT

Repository to download:

https://github.com/keyclaw6/opti-browser-tool

### Mission

Audit whether Opti Browser Tool can safely execute untrusted candidate harness
code and operate a long-running auto-research campaign without corrupting
trusted evidence, leaking credentials or holdout data, exceeding authority or
budgets, becoming unrecoverable, or relying on undisclosed manual intervention.

This part answers:

> Can the implemented system preserve its trust boundary and operate repeatedly
> and recoverably when processes crash, commands race, credentials expire,
> candidates are hostile, or stopping conditions fire?

Do not independently re-audit benchmark selection/environments (Part 1) or
statistical gate validity, attribution quality, and judge calibration (Part 2).
Inspect those only at operational interfaces: who can read/write them, what
process executes them, how failures affect state, and whether enforcement is
real.

### Repository and commit workflow

You have full local clone, inspection, safe-test, file-write, commit, and push
capability. Use it to complete the audit and deliver the report through Git.
Do not change product code, tests, project documentation, manifests, or audit
prompts. The only tracked change on your branch must be this part's assigned
report. Do not access real credentials, invoke real sites, or run destructive
fault injections against non-disposable state. Propose missing fault tests
rather than implementing product changes.

Keep the investigation inside this prompt's scope and batch related reads and
searches. Do not install real browser/model infrastructure merely to expand the
audit. Never print secret values.

Start with:

```bash
git clone --branch main --single-branch https://github.com/keyclaw6/opti-browser-tool.git
cd opti-browser-tool
REVIEWED_SHA="$(git rev-parse HEAD)"
BRANCH="codex/audit-part-3-operations-$(git rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
git switch -c "$BRANCH"
git rev-parse "$REVIEWED_SHA"
git status --short --branch
```

Record `REVIEWED_SHA` in the report.

### Evidence and severity

- `PROJECT_CHARTER.md` and Accepted ADRs are binding.
- `docs/DECISION_REGISTER.md` is authoritative for status.
- Prose is not confinement, atomicity, autonomy, or a safety interlock.
- Editing-time optimizer confinement and candidate execution-time confinement
  are separate properties.
- A trusted store outside the repo is not protected unless permissions and
  principals make it unreachable.
- Distinguish `verified-real`, `implemented-unverified`, `simulated-only`,
  `documented-only`, `missing`, `externally-blocked`, and `contradicted`.

Severity:

- **P0:** reachable trusted-evidence corruption, false acceptance, credential
  or holdout exposure, or uncontrolled external side effect.
- **P1:** prevents safe activation, deterministic recovery, unattended
  operation, or enforceable stopping.
- **P2:** major operational/security risk that can bias results or lose a campaign.
- **P3:** misleading instructions, weak tests, or nonblocking debt.

Every finding needs `file:line`, confidence, reachable causal path, smallest
fix, and an acceptance test. Redact values; report only secret paths,
permissions, inheritance, and reachability.

### Targeted reading list

1. `AGENTS.md`, `PROJECT_CHARTER.md`, `docs/DECISION_REGISTER.md`.
2. Accepted ADR-0004, ADR-0005, ADR-0015, and ADR-0017; open ADR-0006.
3. `PROGRAM.md`, `docs/BRINGUP_RUNBOOK.md`, `docs/AGENT_HANDOFF.md`.
4. `loop_harness/README.md` and `opti_loop` campaign, conductor, store,
   gitutil, fileguard, manifest, evaluate, gates, verdict, packet, ledger,
   transfer, CLI, and tests.
5. Relevant `opti_eval` command/registry adapters, runner, and result handling.
6. Relevant `opti_judge` evidence, LLM command provider, quarantine, and CLI.
7. `harness/infra/`, `.gitignore`, env guidance, schemas, Makefile, examples,
   and generated packet/instruction code.

Run this compact batch if permitted:

```bash
PYTHONDONTWRITEBYTECODE=1 make loop-test
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=eval_harness/src:loop_harness/src:judge_harness/src python -m opti_loop --help
```

Do not run campaign commands that mutate Git administrative state or a trusted
store. Inspect them statically. Do not repeat Part 1's catalog checks or Part
2's judge tests.

## Audit scope A — actual trust boundary

Identify every principal/process:

- owner/operator and conductor;
- optimizer/editor;
- candidate harness runtime;
- browser/session and source bridge;
- verifier and judge;
- main repo and Git refs;
- candidate worktree;
- trusted store, admissions, corpus, quarantine, and holdout;
- model providers, Docker, browser profiles, and live sites.

Produce a privilege matrix:

`principal · OS user · readable paths · writable paths · inherited environment ·
credentials · sockets · network · process-control rights · resource limits`

Draw the actual data flow:

`trusted base → candidate worktree → candidate execution → trace/result →
verifier/gate input → report/ledger → accepted ref/state → next iteration`

Mark every untrusted-to-trusted transition and the enforcement that validates
it. Separate intended production deployment from current executable behavior.

## Audit scope B — editing and candidate-execution confinement

At the logical editing boundary, inspect handling of:

- base ancestry and commit count;
- forbidden paths, dirty files, renames/deletes, ignored files;
- symlinks/nonregular files and traversal;
- registration/manifest expansion;
- trusted store and campaign path resolution;
- attempts to mutate config, suites, verifiers, gates, admissions, quarantine,
  ledger, refs, or reports.

Do not redo the research meaning of E0; establish only whether the file/state
boundary is enforceable.

Then audit candidate execution separately. Determine exactly how candidate
code is launched and whether it can:

- read conductor environment, dotenvx keys, model credentials, `/proc`,
  browser profiles, Docker socket, main-repo Git internals, trusted store,
  verifier assets, admissions, quarantine, corpus, or holdout;
- write outside its worktree or modify evaluation/trusted inputs;
- fabricate traces, activation evidence, final state, verifier result, or
  bridge result;
- leave child processes alive, race later runs, consume unbounded resources,
  or exfiltrate over the network.

Inspect actual OS users, mounts, file ownership/modes, environment
sanitization, subprocess launch, namespaces/containers, network policy,
resource limits, process-group termination, and cleanup. If these are only a
runbook requirement, say so.

## Audit scope C — trusted-store and acceptance-record integrity

Review:

- store-root and campaign-ID path safety;
- permissions, ownership, umask, symlinks, and campaign isolation;
- file replacement, JSONL appends, durability, and tamper evidence;
- immutability/overwrite behavior of iterations and artifacts;
- relationship among accepted Git ref, campaign state, ledger, learnings,
  manifest snapshot, gate report, evaluation artifacts, and main branch;
- evidence identity/content binding before reuse;
- corrupt, truncated, missing, or attacker-modified state;
- collision across campaigns or worktrees;
- ability to erase evidence of a failed or unsafe attempt.

Write the exact accepted-iteration mutation order from source. For every write,
state what a crash before and after it leaves behind and what restart will do.
One Python function is not an atomic multi-file transaction.

## Audit scope D — crash, concurrency, idempotency, and recovery

Statically fault-model these points:

- worktree creation/removal;
- baseline/regression execution;
- packet and pending state;
- manifest ingestion;
- each evaluation rung at the process boundary;
- gate report and attribution snapshot;
- ledger and learnings append;
- accepted-ref update;
- campaign-state update;
- cleanup, merge/push, notification, and transfer scheduling.

Assess:

- exactly-once acceptance and recording;
- locks, leases, transaction IDs, journals, or commit markers;
- idempotent retry and deterministic recovery;
- duplicate/selectively repeated iterations;
- orphan worktrees, processes, browsers, containers, and artifacts;
- disk full, corrupt JSON/JSONL, reboot, permissions, auth expiry, timeout,
  browser hang, bridge/verifier/judge failure, network loss, and push failure;
- bounded retry/backoff and per-task resume;
- campaign resume after code/schema upgrades.

Analyze two concurrent `start` calls, two concurrent `run-iteration` calls, and
overlapping different campaigns. State the minimal safe fault-injection tests
needed before activation.

## Audit scope E — actual unattended control loop

Walk through 25 hypothetical iterations:

`preflight → initialize → measure noise → start → launch confined optimizer →
deliver packet → receive commit/manifest → evaluate → record → report/escalate
→ continue, transfer, pause, or stop`

For each transition identify:

- executable command/scheduler;
- who invokes it;
- manual handoff;
- persisted state;
- timeout/recovery;
- notification/escalation;
- cleanup and next-step trigger.

Follow `README.md`, `PROGRAM.md`, `docs/BRINGUP_RUNBOOK.md`, generated packet
text, CLI help, examples, and Make targets literally. Report nonexistent
commands, wrong paths, missing flags/dependencies, misleading exit codes, and
claims stronger than implementation.

Classify the system today as:

- autonomous campaign runner;
- operator-driven protocol over reliable primitives;
- simulated loop shell;
- documentation/contract scaffold.

Do not infer autonomy from a documented sequence.

## Audit scope F — stop, budget, transfer, and reporting enforcement

Verify executable enforcement—not printed recommendations—of:

- owner stop;
- per-task, iteration, and campaign wall-time/token/money budgets;
- CPU, memory, disk, and process limits where promised;
- consecutive-nonacceptance/plateau and diminishing-return stops;
- quarantine/owner escalation;
- failed-transfer pause;
- holdout and transfer cadence;
- merge/push/report authorization.

At the transfer interface, inspect whether inputs are bound to accepted/base
SHAs, task set, model snapshots, repeats, uncertainty, and an immutable
checkpoint; whether fabricated/partial/stale deltas are rejected; and whether a
failed criterion actually changes campaign state. Leave statistical adequacy
of the criterion to Part 2.

Determine what happens if no changes are accepted and a checkpoint scheduled
“every five accepted iterations” never fires.

## Audit scope G — secrets, commands, and live-site safety

Without revealing any values, audit:

- encrypted dotenvx source files and exclusion of `.env.keys` and private keys;
- key ownership/permissions;
- secret inheritance into candidate, bridge, browser, verifier, judge, and
  child processes;
- logs, stderr, exceptions, traces, screenshots, artifacts, crash dumps, and
  exports;
- redaction before model visibility or export.

Inspect external-command boundaries:

- `shell=True`;
- string/placeholder interpolation;
- argument construction and executable lookup;
- working directory and environment overrides;
- untrusted paths, campaign IDs, manifests, JSON, artifact URIs, and filenames.

Assess prompt injection and exfiltration through pages, accessibility trees,
screenshots, traces, tool output, and judge prompts at the privilege boundary.

ADR-0006 is open. Determine whether real live-site execution is technically
blocked until the policy is accepted and the owner authorizes it. Identify any
implemented destructive-action interlock, allowlist, account isolation, and
emergency stop. Prose is not an interlock.

## Audit scope H — operational observability and YAGNI

Determine whether an operator can detect, without exposing holdout content:

- ref/state/ledger split-brain;
- stalled or orphaned work;
- environment/auth drift;
- repeated invalid runs;
- verifier/quarantine anomalies;
- runaway cost or storage;
- failed cleanup or transfer reversal.

Review audit-log integrity and retention. The optimizer/candidate must not erase
evidence.

Apply YAGNI to fixes: prefer the smallest enforceable boundary, lock/journal,
recovery marker, state machine, resource limit, or corrected claim. Do not
recommend a speculative distributed platform where a confined single-host
mechanism suffices.

## High-risk hypotheses requiring explicit disposition

Report each as `HELD`, `DEFEATED`, `NOT IMPLEMENTED`, or `NOT TESTABLE`:

1. Candidate code executes with conductor credentials/store access despite
   editor confinement.
2. “Outside the repo” is treated as sufficient store security.
3. Acceptance can split across report, ledger, Git ref, and state after crash.
4. Concurrent commands can duplicate/overwrite an iteration.
5. JSONL append/file replacement provides weaker durability than claimed.
6. Incomplete/corrupt evidence can be resumed or reused as complete.
7. Surviving child processes/shared browser state influence later runs.
8. The loop requires a human to launch or repair each iteration.
9. Stops and budgets report violations but do not prevent continuation.
10. Transfer accepts identity-unbound inputs or cannot pause the campaign.
11. Candidate/child processes inherit unnecessary secrets.
12. Live-site execution is possible while ADR-0006 remains unresolved.
13. CLI/runbook/packet claims atomic or autonomous behavior that is only prose.
14. No signal reliably exposes split-brain, stalled work, runaway cost, or
    failed cleanup.

## Required report

Write the Markdown report at:

`docs/review-reports/opti-audit-part-3-operations.md`

Use this structure:

1. **Scope verdict** — `YES / CONDITIONAL / NO` for candidate confinement,
   trusted-state integrity, crash recovery, unattended operation, stop/budget/
   transfer enforcement, and secrets/live-site safety.
2. **Reviewed SHA and checks**.
3. **Trust-boundary diagram and privilege matrix**.
4. **Acceptance write/crash map**.
5. **25-iteration autonomy walkthrough**.
6. **Operational claim-to-evidence matrix**:
   `property · source · enforcement · positive test · missing/negative test ·
   real evidence · implementation state · consequence`.
7. **Findings** — IDs `OPS-001` onward, P0→P3.
8. **High-risk hypothesis disposition**.
9. **Minimum fault/security tests required before activation**.
10. **Dependency-ordered YAGNI remediation path**.
11. **Cross-part handoff** — at most five interface questions for Parts 1 or 2.
12. **Direct answers**:
    - Can candidate code access secrets or forge trusted evidence?
    - Can acceptance commit exactly once across all trusted records?
    - Can every state-transition crash recover safely?
    - Can concurrent commands corrupt work?
    - Are stops and budgets preventative?
    - Does failed transfer actually halt the campaign?
    - Is live-site use blocked pending policy/authorization?
    - Can 25 iterations run without undisclosed human orchestration?
    - What minimum blocker set changes this part's verdict?

End with:

> **OPERATIONS SAFE FOR AN UNATTENDED REAL CAMPAIGN: YES/NO**

If `NO`, follow with the shortest dependency-ordered blocker list.

### Commit and push the report

Before committing, ensure no tracked file except the assigned report changed.
Discard only changes generated by your own inspection commands.

```bash
git status --short
git add docs/review-reports/opti-audit-part-3-operations.md
git diff --cached --name-only
git diff --cached --check
git commit -m "docs: add operations audit report"
git push -u origin HEAD
git branch --show-current
git rev-parse HEAD
```

The staged-name output must contain exactly the report path. Do not commit
generated files or fixes discovered during the audit.

After pushing, reply with only:

- reviewed base SHA;
- report path;
- pushed branch name;
- report commit SHA; and
- push status.

Do not paste the report into chat. If pushing is impossible, create a one-commit
`git format-patch` artifact and return that file instead of its text.
