# Opti Browser Tool — Part 3 Security and Operations Audit

Date: 2026-07-14
Reviewed base SHA: `6cad1f09e0a1bf3f5a1a850bbd51d5a1600d585c`

## 1. Scope verdict

| Property | Verdict | Current implementation state | Short reason |
|---|---|---|---|
| Candidate confinement | **NO** | Editing guard partially implemented and tested; execution confinement missing/contradicted | A linked-worktree optimizer can affect the trusted Git namespace, ignored or raced bytes are evaluated outside the candidate commit, and command-adapter execution runs with conductor authority. |
| Trusted-state integrity | **NO** | Partially implemented, not transactionally safe | Individual JSON replacements exist, but acceptance spans mutable artifacts, JSONL, a Git ref, state, and cleanup without a journal, lock, CAS, immutable receipt, or reconciliation. |
| Crash recovery | **NO** | Missing | A crash during any evaluation rung leaves an existing output directory that blocks retry. Later crashes split report, cluster register, ledger, learnings, accepted ref, and state. |
| Unattended operation | **NO** | Simulated-only/operator-driven | There is no preflight command, optimizer launcher, outer scheduler, heartbeat, next-iteration trigger, report/push worker, or recovery command. |
| Stop, budget, and transfer enforcement | **NO** | Documented-only or stateless simulation | The runbook's stop and spend limits do not exist in campaign state or launch checks. Transfer accepts unbound floats and cannot pause a campaign. |
| Secrets and live-site safety | **NO** | Key-file hygiene partially verified; runtime boundary missing | Command children inherit the conductor environment, home, filesystem, Docker socket, network, and process rights; logs are unredacted; ADR-0006 is prose-only and no technical live-site interlock exists. |

The strongest positive controls are real but narrow: the final commit diff is allowlisted and path-checked (`loop_harness/src/opti_loop/fileguard.py:37-58,95-123`), a typed verdict prevents simulated results from advancing (`loop_harness/src/opti_loop/verdict.py:23-51`), correctly tagged restricted evidence is filtered at the judge read API (`judge_harness/src/opti_judge/evidence.py:43-60,76-121`), and the default fixture is non-reportable. None establishes a safe hostile-code runtime or recoverable campaign transaction.

The system today is best classified as a **simulated loop shell with operator-driven single-iteration primitives**. It is not an autonomous campaign runner, and the primitives are not yet reliable under crash or concurrency.

## 2. Reviewed SHA and checks

The audit used the existing detached worktree as commissioned. Pre-existing review-orchestration changes were preserved; no product, test, prompt, manifest, or existing documentation file was modified by this review.

| Check | Result |
|---|---|
| `git rev-parse HEAD` | `6cad1f09e0a1bf3f5a1a850bbd51d5a1600d585c` |
| `PYTHONDONTWRITEBYTECODE=1 make loop-test` | **PASS** — 26 tests, 0 failures, 4.75 seconds |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=eval_harness/src:loop_harness/src:judge_harness/src python -m opti_loop --help` | **PASS**, exit 0; one-shot subcommands only |
| Disposable Git replacement probe | Before `git replace`, `base..candidate` reported `A forbidden.txt`; afterward it reported no diff and ancestry still returned 0/success |
| `git check-ignore -v --no-index harness/components/policy/optimizer-only.log` | Confirmed `.gitignore:11` hides a regular optimizer-controlled component file from default porcelain status |
| Store namespace pure-path probe | `TrustedStore(Path('/trusted/root'), '../../escape').campaign_dir.resolve()` became `/escape`; an absolute ID became `/absolute/escape` |
| Nonexistent packet command probe: `python -m opti_loop gate --help` | **Expected negative:** exit 2, invalid subcommand |
| Documented post-subcommand store flag probe | **Expected negative:** `opti-loop init --campaign ... --store-root ...` exited 2 before any write; the global option is accepted only before the subcommand |
| Rejecting transfer probe | Returned `REJECT_TRANSFER_BET` but exit 0 and changed no campaign state |
| Non-finite transfer probe | One input `NaN` returned `transfer_supported`, exit 0 |
| Current secret-file/path inspection, values never read | No `.env*` path is tracked or present in reachable history; `.env.keys*` is ignored; host key is mode 0600 in a mode-0700 directory; public key file is 0644 |
| Current runtime-principal inspection | CLI user belongs to `docker`; `/var/run/docker.sock` is `root:docker` mode 0660; a same-user child can control the daemon |
| Generated Python artifacts | None (`PYTHONDONTWRITEBYTECODE=1`) |

Safe probes used only disposable state or read-only inspection. No campaign command that would mutate the project Git administration or a trusted store was run. No credential value, holdout material, real site, model endpoint, or browser environment was accessed.

## 3. Trust-boundary diagram and privilege matrix

### Actual executable data flow

```text
 TRUSTED: campaign state.accepted_base_sha and owner repository/common .git
       |
       | conductor: git worktree add --detach
       v
 [candidate linked worktree] <--------- optimizer/editor (external/manual)
       |                                  writes components, shared Git objects/admin,
       | candidate HEAD + manifest        and any ignored/raced runtime bytes
       |  U -> T transition #1
       v
 conductor snapshots manifest -> E0 commit diff / manifest / registration / lint
       |
       | E2/E3/E4/E5 evaluate the still-live candidate worktree
       v
 CommandAdapter: /bin/bash, conductor UID, copied environment, inherited cwd/home,
 network/sockets/process rights, trusted-store task output paths
       |
       | bridge/candidate writes bridge-result.json, logs, trace/artifacts
       |  U -> T transition #2 (no OS or authenticity boundary)
       v
 opti-eval TaskResult -> admission-string check -> optional T1 -> comparison/gate
       |
       |  U -> T transition #3 (missing/malformed trace can still be benchmark)
       v
 gate report -> cluster register -> ledger -> learnings -> accepted Git ref -> state
       |                                               U -> T transition #4
       v
 worktree removal; no scheduler/report/push/transfer/notification trigger
```

On the current fixture path, no browser candidate executes and all evidence remains simulated. On the intended command/source-bridge path, the bridge is the process boundary and currently has the same authority as the conductor. Moving the store outside the repository does not protect it from that process.

### Enforcement at each untrusted-to-trusted transition

| Transition | Implemented enforcement | What remains untrusted or bypassable |
|---|---|---|
| Optimizer tree to candidate commit | Ancestry, final-diff allowlist, path checks, regular-file checks, dirty porcelain check, manifest structure, registration, whole-tree token lint | Shared replace refs/grafts/config; no one-commit check; ignored files absent from porcelain; live tree stays writable after E0; lint is not a content identity. |
| Candidate execution to result/trace | Task/source/status/reward shape validation and bridge timeout | Same UID/env/filesystem/network; child receives trusted output path; bridge self-reports verifier/result; no native-verifier attestation; descendants and output size unbounded. |
| Result/trace to benchmark verdict | Adapter reportability, admission strings/checksum string, optional auto-T1, deterministic comparison, typed verdict | No trace is required; malformed traces are skipped; E1 says `pass` while dynamic activation is pending; admission does not prove the admitted binary ran. |
| Verdict to accepted records | Per-file JSON replacement, ledger fields include base/candidate SHA and run identity, accepted ref preserves candidate object | No lock/journal/transaction ID/commit marker/CAS/fsync chain; cluster, ledger, learnings, ref, state, and cleanup can split. |

### Privilege matrix

`Actual` means enforced by shipped executable code or verified current host state. `Intended` means the production design in ADR-0017 and the bring-up runbook.

| Principal/process | OS user | Readable paths | Writable paths | Inherited environment | Credentials | Sockets | Network | Process-control rights | Resource limits |
|---|---|---|---|---|---|---|---|---|---|
| Owner/operator and conductor | Actual CLI invoker; intended `opti-conductor` | Repo, common Git dir, trusted store, home/auth, eval assets, future holdout | Repo/Git refs, store, environments, worktree admin | Full invoking environment | Dotenvx/model/site auth when launched through that environment | Current user can access the Docker socket | Unrestricted host sockets | Normal same-user process control; launches all children | None at campaign level |
| Optimizer/editor | No launcher or UID transition in code; intended separate `opti-optimizer` | Actual access is external and unconstrained by this code. Intended packet/analysis plus candidate components | Intended components + manifest; actual linked Git commit also requires common Git objects and worktree admin writes | No sanitizer contract is implemented | No credential-denial contract is implemented | No implemented policy | No implemented policy | No managed job, PID, heartbeat, or kill boundary | None implemented |
| Candidate harness runtime | Command child runs as conductor | Worktree, trusted task/store path and, by same UID, repo, store, home, `/proc`, profiles, future holdout | Trusted task output and any conductor-writable path | `os.environ.copy()` plus adapter extras | Decrypted/injected credentials can flow to it | Inherits accessible host sockets, including Docker on reviewed host | Unrestricted host network | Can fork, signal same-UID processes, background descendants | Only a timeout on the immediate shell; no CPU/memory/PID/disk/output limits |
| Browser/session/source bridge | Real bridge/profile broker missing; command shell is executable placeholder | Same as candidate command unless external command independently confines itself | Same as conductor child; browser/profile locations unspecified | Full copied environment | Any invoking-environment/browser-profile credentials | Inherited host sockets | Unrestricted | Can launch browsers/containers and leave them alive | Immediate-shell timeout only |
| Native verifier | Production invocation not attested; bridge reports result. Probe verifier is a same-UID shell | Probe/task/trace plus all same-user paths | Result path plus same-user paths | Inherited environment | Same inherited credential reachability | Inherited host sockets | Unrestricted | Normal child/fork rights | 120-second immediate-shell timeout only |
| T1 verifier cross-check | Conductor Python process | Trace, task, quarantine | Quarantine queue | Conductor environment, though it does not need secrets | Same process credential reachability | Host sockets inherited | Host access inherited | Conductor rights | None |
| T2 judges / Analyst | Fixture today; intended command provider runs as conductor | Role files and page/trace evidence; command child can read host paths | Intended analysis only; executable command is not filesystem-confined | Command provider inherits conductor environment | Command provider inherits credentials; HTTP provider reads judge env key | Host sockets inherited | Command/HTTP network available | Command may fork or, if wired to a tool-capable agent, act beyond judgment | 300-second immediate process timeout; no sandbox/tool boundary |
| Main repo and Git refs | Owner filesystem principal | Readable to conductor; optimizer must reach shared objects to commit in linked worktree | Conductor; actual same-user optimizer can write shared Git metadata | Git config/environment not sanitized | Remote credential helper/agent reachability depends on host session | Git/SSH agent sockets may be inherited by Git commands | Remotes available to host commands | Git hooks/config/replace namespace not isolated | None |
| Candidate worktree | Created by conductor inside campaign store | Conductor and whichever principal is externally granted access | Full tree for conductor; intended optimizer subset not mounted/chowned by code | N/A | N/A | N/A | N/A | Removal errors ignored | Filesystem only |
| Store, admissions, corpus, quarantine | Owner-only by prose; code verifies only that root is outside repo | Ambient filesystem modes/parents; same-UID candidate command can read all | Conductor and same-UID candidate command; raw campaign IDs can escape root | N/A | May contain sensitive evidence and future holdout | N/A | N/A | N/A | No quota/retention enforcement |
| Hidden holdout | Not implemented; intended under owner store before iteration 1 | No current object/mount boundary. Future same-UID candidate child could traverse it | Conductor intended | N/A | Potential private verifier/task evidence | N/A | Evaluation network unspecified | N/A | N/A |
| Model providers / Docker / live sites | External services invoked from conductor context | Tokens/auth/profile state available through environment/home | External side effects depend on arbitrary command | Conductor environment reaches clients | Provider/site credentials may be inherited | Docker/browser/agent sockets may be reachable | Unrestricted; no egress allowlist | Docker socket grants daemon control on reviewed host | Provider timeout only where command supplies one |

The intended two-user model is internally incomplete: the optimizer is supposed to be unable to reach the main `.git` and trusted store (`docs/BRINGUP_RUNBOOK.md:27-34`) while also committing in a linked worktree whose common object/admin namespace is the main repository (`loop_harness/src/opti_loop/gitutil.py:88-94`). The candidate worktree is nested inside the supposedly unreadable campaign directory (`loop_harness/src/opti_loop/store.py:119-125`). No mount, ACL, broker, standalone clone, ownership transition, or packet-delivery mechanism resolves this.

The external-command boundary adds no compensating control. `CommandAdapter` formats `{task_json}`, `{result_json}`, `{task_id}`, `{source}`, and `{output_dir}` directly into an operator-configured string and passes it to inherited-PATH `/bin/bash` with `shell=True` and no explicit working directory (`eval_harness/src/opti_eval/adapters/command.py:15-16,45-86`). The judge and probe providers likewise execute shell strings (`judge_harness/src/opti_judge/llm.py:65-76`; `judge_harness/src/opti_judge/probekit.py:116-145`). An unquoted placeholder containing shell metacharacters therefore becomes command syntax; executable lookup, shell startup behavior, and working directory are ambient. The production page/accessibility/screenshot bridge is not implemented, so its exact prompt-injection path is **not implemented** rather than testable here. Once an arbitrary bridge or command judge supplies those materials, however, there is no redaction or privilege-reducing broker before model visibility, and a prompt-injected tool-capable process would retain the same filesystem, credential, socket, and network authority shown above. Raw stdout/stderr and exception tails can persist or be re-presented without secret filtering (`command.py:88-120`; `llm.py:70-76`).

## 4. Acceptance write/crash map

The source labels `run_iteration` a single atomic transaction (`loop_harness/src/opti_loop/conductor.py:11-15,174-175`), and accepted ADR-0015 makes that property binding (`docs/adr/0015-auto-research-loop-architecture.md:53-60`). The implementation is the following ordered sequence of independent writes.

### Start/pending preparation

| Order | Mutation and source | Crash before / after | What restart does |
|---|---|---|---|
| S1 | Remove an existing candidate worktree, then add a detached linked worktree at accepted base (`gitutil.py:88-98`; `conductor.py:98-100`) | Before: old worktree may remain. After: new worktree/admin entry exists with no campaign receipt. | A later `start` force-removes it; errors are ignored. A second concurrent `start` may remove a live worktree. |
| S2 | `open_iteration` creates `iter-N`, increments `current_iteration`, and replaces state while `pending_iteration` is still zero (`campaign.py:92-97`) | Before: N is reusable. After: N is consumed but not pending. | `start` opens N+1; N is an unrecorded orphan. |
| S3 | Development baseline run tree: running marker, task files/results, JSONL, summary, completed marker (`conductor.py:107-110`; `eval_harness/src/opti_eval/runner.py:63-132`) | Mid-run leaves a partial tree. | No per-task resume. Because state is not pending, next `start` moves to N+1; retrying the same path fails on existing directory. |
| S4 | Regression baseline run tree (`conductor.py:111-116`) | Same partial-tree risk; in-memory regression results are not yet in persisted state. | Orphan/skip; no repair command. |
| S5 | Optional drift JSON replacement (`conductor.py:118-126`) | May exist without a pending iteration. | Ignored as an orphan. |
| S6 | Stub analysis direct writes (`analyst.py:75-81`) | Can leave partial JSON/Markdown on kill or disk error. | No completion check. |
| S7 | Cluster register direct truncate/rewrite (`conductor.py:132-136`; `clusters.py:28-35`) | Can record failures for an iteration that never becomes pending or truncate the campaign-wide register. | Corrupt JSON aborts later reads; completed mutation is not rolled back. |
| S8 | `packet.json` and `PACKET.md` direct writes (`packet.py:50-52,98-99`) | The two packet forms may disagree or be partial. | No packet receipt/version check. |
| S9 | Persist `pending_iteration`, divergence, and base SHA (`conductor.py:149-152`) | Before: all S1-S8 may be orphaned. After: state finally points to N. | `run-iteration` proceeds without proving S3-S8 are complete or mutually consistent. |

### Gate, record, accept, and cleanup

| Order | Mutation and source | Crash immediately before / after | Restart or retry result |
|---|---|---|---|
| R1 | Snapshot current untrusted `manifest.json` (`conductor.py:188-202`) | Before: no frozen manifest. After: snapshot exists, but candidate HEAD/manifest are not locked against later optimizer mutation. | Retry may snapshot different input for the same N. |
| R2 | E2 smoke run tree (`gates.py:135-146`) | Mid-run leaves partial output. After completion, later crash leaves complete E2 but pending transaction. | Retry calls `run_suite` with `overwrite=False` and immediately fails because the E2 directory exists (`evaluate.py:99-107`; runner `:63-70`). |
| R3 | E3 targeted screen (`gates.py:148-165`) | Same. | Retry is already blocked by R2. |
| R4 | E4 regression treatment (`gates.py:167-181`) | Same. | No rung resume or completed-run reuse. |
| R5 | E5 development treatment and possible quarantine mutation (`gates.py:183-205`; `eligibility.py:100-106`; `quarantine.py:82-110`) | Partial eval or quarantine may persist without verdict. Quarantine is non-atomic whole-file rewrite. | Retry blocked; quarantine can remain detached from any ledger row. |
| R6 | Replace `gate-report.json` (`conductor.py:233`) | Before: evaluations exist without report. After: report may say accepted while nothing else does. | Retry blocked by R2; no recovery consumes the report. |
| R7 | Replace manifest snapshot with conductor attribution/status (`conductor.py:235-241`) | Report and snapshot can split. | No immutable original-ingestion receipt or reconciliation. |
| R8 | Direct rewrite of cluster register for accepted fixes (`conductor.py:246-250`; `clusters.py:34-35`) | Can mark clusters fixed before the campaign accepts the candidate. | Retry blocked; later state/ledger may remain old. |
| R9 | Append ledger row (`conductor.py:252-264`; `store.py:62-65`) | A mid-write can truncate JSONL. After a full append, ledger claims acceptance while ref/state remain old. | JSON parsers can fail on truncated tail; there is no transaction-ID dedupe. |
| R10 | Append learnings template (`conductor.py:265,334-341`; `ledger.py:45-52`) | Ledger can exist without learning, or the append can be partial. | Manual retry can duplicate it. Normal output still contains required `<fill in>` placeholders. |
| R11 | Unconditional `git update-ref` to candidate (`conductor.py:267-281`; `gitutil.py:108-110`) | Before: ledger says accepted but ref is old. After: ref is new while state remains old/pending. | No expected-old CAS and no reconciliation command; retry is blocked. |
| R12 | Mutate accepted base/list/counters/regression memory in RAM, clear pending, then replace state (`conductor.py:270-294`) | Any exception after R11 and before save leaves ref/state split. | `status` trusts state and never compares the ref. |
| R13 | Force-remove worktree and prune; errors ignored (`conductor.py:296-299`; `gitutil.py:96-98`) | State is already committed. Crash/failure leaves worktree, browser/children, and possibly shared state. | Next `start` attempts removal but reports no cleanup failure; descendants are unmanaged. |

There is no R14 for merge, push, owner notification, transfer scheduling, or a completion receipt. The runbook promises a main push after acceptance (`docs/BRINGUP_RUNBOOK.md:166-170`), but source only updates `refs/opti/<campaign>/accepted`. A push failure therefore cannot be represented, retried, or surfaced.

The pivot rejection path is also non-idempotent: report, ledger, state clear, cleanup (`conductor.py:310-331`) with no learning. A crash after its ledger append can duplicate that rejection on retry.

### Durability, immutability, and tamper evidence

- Loop-store replacement writes and closes a temp file, then `os.replace`s it, but does not `fsync` the file or parent directory (`loop_harness/src/opti_loop/store.py:46-55`). This is atomic namespace replacement on ordinary POSIX filesystems, not claimed reboot/power-loss durability.
- JSONL and learnings appends have no lock, explicit flush/fsync, tail checksum, sequence chain, or recovery (`store.py:62-65`; `conductor.py:334-341`).
- Eval JSON replacement fsyncs the temp file but not its directory; eval JSONL is a direct rewrite (`eval_harness/src/opti_eval/util.py:47-66`).
- Cluster, packet, analysis, quarantine, and corpus files use direct writes or unprotected read-modify-write (`clusters.py:34-35`; `packet.py:50-52,98-99`; `analyst.py:75-81`; `quarantine.py:82-110`; `corpus.py:66-83`).
- Iteration directories are not immutable. The shipped forged-report test demonstrates that a pre-existing report is simply overwritten (`loop_harness/tests/test_e2e_loop.py:167-183`).
- There is no content receipt linking gate report, manifest, eval artifacts, admissions, trace/artifact hashes, ledger row, and state. `GateReport` itself omits base/candidate SHA and run identity (`gates.py:39-58`).
- Rejected candidate commits are deliberately unreferenced and garbage-collectable (`conductor.py:296-299`), so store tampering or pruning can erase the only connection to a failed/unsafe attempt.

## 5. Twenty-five-iteration autonomy walkthrough

### Transition mechanics repeated by every iteration

| Transition | Executable command / invoker | Persisted state | Timeout / recovery | Notification / cleanup / next trigger |
|---|---|---|---|---|
| Preflight | No command. Bring-up checklist is prose (`docs/BRINGUP_RUNBOOK.md:175-192`). | None | None | Owner must inspect and authorize manually. `start` does not check the checklist. |
| Initialize | Operator runs `opti-loop init`. | Config, state, ledger, learnings, clusters (`campaign.py:108-146`) | Partial init is unrecoverable: config alone makes `exists()` true. | Prints JSON only. |
| Measure noise | Operator runs `measure-noise`; CLI defaults to 3, runbook requires at least 5 (`cli.py:59-61`; runbook `:108-115`). | Config and separate noise-band file | Fixed run paths prevent clean remeasurement; no lock; cleanup only in Python `finally`. | Prints JSON only. |
| Start | Operator runs `start`. | Baselines, analysis, packet, pending state | Command-level bridge timeouts only; no start deadline, journal, or resume | Prints worktree/packet/instructions. |
| Launch confined optimizer | No executable launcher. External owner/Codex must create a session/user/mount and pass packet. | No job ID/PID/lease/heartbeat | No timeout, watcher, cancellation, or receipt | Manual handoff. |
| Deliver packet | `start` writes packet inside owner store and prints its path. | Packet files | No sanitization/version receipt | Intended optimizer cannot read owner-only store unless an unimplemented mount/copy is added. |
| Receive commit/manifest | No watcher; operator decides it is ready. | Candidate Git objects and worktree manifest | No immutable freeze or deadline | Manual handoff back to conductor. |
| Evaluate and record | Operator runs `run-iteration`. | R1-R13 above | Immediate shell timeout only; no retry/resume | Worktree removal on normal completion only. |
| Report/escalate | `status` can be called manually. | No summary/notification record | Corrupt ledger crashes status | No notification, owner summary, push, or escalation worker. |
| Continue / transfer / pause / stop | Operator chooses another `start` or a stateless transfer command. | Divergence counters only | No campaign lifecycle state | No next-step trigger. |

### Deterministic no-acceptance walk through all 25 iterations

This path is operationally decisive because the runbook requires a pause at 10 consecutive non-acceptances. `S/O/R` below means three undisclosed/manual actions every time: operator `start`, separately launch and hand off an optimizer, then operator `run-iteration`.

| Iteration | Mode stamped by current code | Required actions | What should stop/escalate | What current code actually does |
|---:|---|---|---|---|
| 1 | Cluster-targeted | S/O/R | Nothing yet | Records one result; no next trigger. |
| 2 | Cluster-targeted | S/O/R | Nothing yet | Same. |
| 3 | Cluster-targeted | S/O/R | Nothing yet | Same. |
| 4 | Cluster-targeted | S/O/R | Plateau approaches | Increments `iterations_since_accept`; no pause. |
| 5 | Divergent | S/O/R | Exploration quota/plateau forces divergence | Divergence is stamped, but no report/transfer trigger. |
| 6 | Divergent | S/O/R | Plateau remains | Plateau condition keeps every later iteration divergent. |
| 7 | Divergent | S/O/R | Plateau remains | Continues if operator invokes it. |
| 8 | Divergent | S/O/R | Plateau remains | Continues. |
| 9 | Divergent | S/O/R | Approaching nonacceptance stop | Continues. |
| 10 | Divergent | S/O/R | **Required pause + diminishing-returns report** (`docs/BRINGUP_RUNBOOK.md:159-165`) | No stop field/check/report; iteration 11 remains launchable. |
| 11 | Divergent | S/O/R | Campaign should already be paused | Continues. |
| 12 | Divergent | S/O/R | Paused | Continues. |
| 13 | Divergent | S/O/R | Paused | Continues. |
| 14 | Divergent | S/O/R | Paused | Continues. |
| 15 | Divergent | S/O/R | Paused | Continues. |
| 16 | Divergent | S/O/R | Paused | Continues. |
| 17 | Divergent | S/O/R | Paused | Continues. |
| 18 | Divergent | S/O/R | Paused | Continues. |
| 19 | Divergent | S/O/R | Paused | Continues. |
| 20 | Divergent | S/O/R | Paused | Continues. |
| 21 | Divergent | S/O/R | Paused | Continues. |
| 22 | Divergent | S/O/R | Paused | Continues. |
| 23 | Divergent | S/O/R | Paused | Continues. |
| 24 | Divergent | S/O/R | Paused | Continues. |
| 25 | Divergent | S/O/R | Campaign ceiling/final report point | No money/token/wall-time check and no final report; iteration 26 is launchable. |

With no accepted changes, `accepted_iterations` remains empty, so a checkpoint scheduled every five accepted iterations never becomes due. No fallback checkpoint exists. If acceptances do occur, source still never schedules the checkpoint; an operator must notice the count, create external runs, and manually pass unbound deltas to `transfer-eval`.

Minimum human orchestration for this path is 25 `start` calls, 25 optimizer-session launches and packet deliveries, 25 completion judgments/handoffs, and 25 `run-iteration` calls, plus learning repair, status inspection, reports, push, and any cleanup. That is not unattended operation.

## 6. Operational claim-to-evidence matrix

| Property | Source claim | Executable enforcement | Positive test/evidence | Missing or negative test | Real evidence | Implementation state | Consequence |
|---|---|---|---|---|---|---|---|
| Final-diff path containment | ADR-0005 `:23-25`; ADR-0015 `:55-58` | Ancestry, commit diff, allowlist, path/regular-file, dirty check | Unit and E2E forbidden committed edit pass | Replace refs/grafts/config; ignored file; post-E0 race; exactly-one commit | Disposable replace probe defeated diff | **Contradicted as a trust boundary** | Forbidden trusted-plane edits can be hidden. |
| Exactly one candidate commit | PROGRAM `:33-36,49` | None; `commits_between` exists but is unused (`gitutil.py:53-55`) | None | Two commits, forbidden-then-revert history, empty final diff | Static source | **Missing** | Accepted ancestry can contain unreviewed intermediate objects; attribution contract unenforced. |
| Candidate runtime confinement | ADR-0017 `:17-18`; runbook `:18-34` | None in launcher/adapter; README admits deployment-only (`loop_harness/README.md:74-78`) | None | Secret/store/ref/socket/network/process denial | Current child would share Docker-capable UID | **Documented-only** | Credential theft, evidence forgery, side effects, exfiltration. |
| Owner-only store | ADR-0015 `:55`; README `:49-51` | Store root must resolve outside repo | Path-under-repo rejection tests exist indirectly | Owner/mode/symlink/campaign-ID/separate-UID tests | Pure-path probe escaped root; ambient umask 0022 | **Partially implemented, contradicted** | Store/holdout may be reachable, aliased, or overwritten. |
| Typed benchmark advancement | README `:58-62`; verdict source | `accepted && benchmark` predicate | Verdict and simulated-inert tests pass | Forgeable command result/missing trace | E2E benchmark acceptance is trace-free | **Implemented but upstream evidence untrusted** | Correct type wraps an incorrectly elevated evidence class. |
| Dynamic E1 activation | ADR-0005 `:25-27` | Static registration; gate labels dynamic audit pending but rung `pass` | Registration tests | Missing activation trace must invalidate | Current E2E accepts without trace | **Contradicted** | Inert or fabricated changes can pass E1. |
| T1 before benchmark evidence | Eligibility doc `:8-15` | T1 over traces that happen to exist | Suspicious trace routes to quarantine | Missing/malformed trace, missing judge module | Missing/malformed trace is silently skipped | **Contradicted** | False benchmark acceptance. |
| Atomic gate/record/accept | ADR-0015 `:55`; PROGRAM `:37`; conductor docstring | Sequential R1-R13 | Happy-path E2E only | Kill/error at every boundary, disk full, ref failure | Static write map | **Contradicted** | Split-brain and unrecoverable pending iterations. |
| Exactly-once / concurrency | “one transaction” prose | Sequential pending check only | Sequential second start rejected | Concurrent start/run; CAS; duplicate ledger | No lock/journal/CAS in repository | **Missing** | Duplicate records, destroyed worktree, last-writer state. |
| Durable/tamper-evident audit log | ADR-0004 append-only intent `:17-25` | Plain JSONL append | Rows contain useful fields | fsync, tail recovery, hash chain, immutable receipt | Store append lacks all | **Missing** | Truncation/tampering is undetected or crashes readers. |
| Per-task/rung recovery | ADR-0005 deferred requirement `:48-53` | None | None | Crash/hang at task/rung; resume exact completed set | Existing directory blocks rerun | **Missing** | Manual deletion/full rerun required. |
| Unattended campaign | Runbook `:3-6,151-152` | One-shot CLI primitives | Happy-path one iteration | 25-iteration driver, launcher, heartbeat, notifications | Literal walkthrough requires manual S/O/R | **Missing / simulated-only** | Cannot operate unattended. |
| Preventative stops and budgets | Runbook `:154-170` | Immediate shell timeout only | Timeout error result | Owner stop, cost/token/wall/CPU/mem/PID/disk, plateau, campaign ceiling | No relevant state/config checks | **Documented-only** | Operator can continue after every required stop. |
| Transfer checkpoint enforcement | Campaign config `:45-49`; runbook `:138-148` | Stateless plan and median function | Finite median calculation | Identity, panel completeness, finite values, persistence, pause | Reject exits 0; NaN supports transfer | **Simulated-only / contradicted** | Fabricated/stale transfer cannot halt campaign. |
| Secret handling/redaction | AGENTS `:5-7`; charter `:51-53`; ADR-0004 `:27-35` | Git ignores key files; evidence read filter honors writer tags | Current key file mode 0600; restricted-tag tests | Env/canary, stdout/stderr/errors/trace/screenshot/export redaction | Command copies full env and raw logs | **Partially implemented, runtime missing** | Credentials/sensitive content can reach candidate, logs, models, exports. |
| Live-site block | ADR-0006 `:28-30`; PROGRAM `:56` | None | Default fixture avoids sites | Arbitrary command/network/destructive action before approval | Command adapter has unrestricted shell/network | **Documented-only** | Unauthorized external side effects are reachable. |
| Operational health visibility | Runbook reporting `:166-170` | Manual `status`: state plus ledger count/tail | Basic status fields | Ref/state/report reconciliation, stale PID, auth/disk/cost/transfer/cleanup | Status code `cli.py:119-134` omits all | **Missing** | Split-brain/runaway/stall can remain invisible. |

## 7. Findings

### OPS-001 — P0 — Shared Git administration lets the optimizer defeat E0

- **Evidence / state:** `gitutil._run` invokes ordinary Git without a clean environment or `GIT_NO_REPLACE_OBJECTS` (`loop_harness/src/opti_loop/gitutil.py:25-33`). E0 ancestry and diff are ordinary `merge-base` and `git diff` (`gitutil.py:44-74`), then trusted by `fileguard.check_candidate` (`fileguard.py:95-118`). The optimizer is required to commit in a linked worktree created from the trusted repository (`gitutil.py:88-94`), so its Git operations share the common object/admin namespace. **Implementation state: contradicted.**
- **Confidence:** High; reproduced in a disposable bare repo.
- **Reachable causal path:** Candidate commits a forbidden eval/gate change C over trusted base B -> candidate creates `refs/replace/B -> C` in the shared common Git dir -> conductor asks Git whether B is an ancestor and for `B..C` -> Git resolves both through replacement, reports success and an empty diff -> E0 sees no forbidden path -> malicious candidate tree is evaluated and can become the accepted ref. The audit reproduction changed `A forbidden.txt` to an empty diff while ancestry still returned success.
- **Consequence:** Reachable trusted-plane corruption and false acceptance. Direct ref/config/graft manipulation is also unconfined in the actual same-user setup.
- **Smallest fix:** Do not expose the trusted repository's common Git directory to the optimizer. Give it a disposable standalone repository/no remote, or export only component files; have the conductor import a patch/bundle, create the single candidate commit owner-side, and verify it with a sanitized Git environment. Disable replacements/grafts defensively, but do not treat that flag as the primary boundary.
- **Acceptance test:** From the real optimizer UID, attempt replace refs, grafts, config includes, hook/ref writes, and a forbidden candidate commit. All trusted Git writes must be denied, and owner-side E0 must still report the forbidden path.

### OPS-002 — P0 — Candidate/bridge execution has conductor secrets and trusted-store authority

- **Evidence / state:** `CommandAdapter` copies all of `os.environ`, passes resolved trusted-store task/result/output paths, and invokes `/bin/bash` with `shell=True` as the current user (`eval_harness/src/opti_eval/adapters/command.py:45-87`). It stores stdout/stderr verbatim (`:88-120`). Source/probe/judge command providers use the same pattern (`judge_harness/src/opti_judge/probekit.py:116-145`; `judge_harness/src/opti_judge/llm.py:65-82`). The README explicitly says deployment isolation is a requirement, not code (`loop_harness/README.md:74-78`). **Implementation state: missing at candidate execution.**
- **Confidence:** High. Current host inspection also confirmed the invoking user can access the Docker socket.
- **Reachable causal path:** Accepted-base worktree -> E2-E5 -> command bridge loads hostile candidate harness -> child reads environment/home/key paths, `/proc`, browser profiles, repository/common Git, store/admissions/quarantine/future holdout, and Docker socket -> child modifies trusted inputs or emits secrets to raw logs/network -> gate consumes those outputs.
- **Consequence:** Credential/holdout exposure, trusted-evidence forgery, main-repo/ref mutation, root-equivalent Docker actions, denial of service, and network exfiltration.
- **Smallest fix:** One single-host sandbox wrapper for every candidate task: distinct UID/user namespace, immutable candidate snapshot, read-only eval assets, private scratch output, empty allowlisted environment, no home/store/holdout/main-Git/profile/Docker mounts, deny network by default (or explicit benchmark proxy allowlist), and a cgroup/process group. The trusted bridge/verifier remains outside and copies validated artifacts into the store after the sandbox exits.
- **Acceptance test:** A hostile candidate probes decoy env credentials, key/home paths, store/holdout, main Git refs, `/proc` peers, Docker socket, arbitrary filesystem writes, network/DNS, fork/background, and signals. Every unauthorized operation must fail; canaries must not appear in logs, traces, model input, or exports.

### OPS-003 — P0 — E0 does not bind the bytes that treatment execution uses

- **Evidence / state:** Dirty detection uses default `git status --porcelain`, which omits ignored files (`loop_harness/src/opti_loop/gitutil.py:77-85`). This repository ignores `*.log` and `artifacts/` (`.gitignore:7,11`); read-only probes confirmed those paths can exist inside `harness/components`. Whole-tree lint reads them but only applies a denylist and produces no content receipt (`loop_harness/src/opti_loop/lint.py:160-186`). E0 finishes before E2-E5 execute the same still-writable tree (`gates.py:93-185`). **Implementation state: contradicted.**
- **Confidence:** High.
- **Reachable causal path:** Candidate commits an allowed loader change -> places behavior/config in an ignored regular file not present in candidate SHA or manifest -> porcelain reports clean and registration sees only committed paths -> lint finds no known benchmark token -> evaluation reads ignored payload. Alternatively a still-running optimizer changes tracked/ignored bytes after E0. Gate accepts candidate SHA C even though the measured treatment bytes are C plus uncommitted payload; next worktree at C does not contain the measured behavior.
- **Consequence:** False acceptance, false activation/attribution evidence, non-reproducible treatment, and an avenue to hide benchmark-specific behavior.
- **Smallest fix:** After manifest receipt, stop/revoke optimizer writes and evaluate a fresh read-only checkout/materialization derived only from the candidate commit. Hash the execution tree and bind it to every run/report. Also enumerate ignored/untracked paths with `--ignored` and reject them at receipt.
- **Acceptance test:** An ignored registered payload and a barrier-controlled post-E0 mutation must be unavailable to the treatment process or make E0 invalid; the execution-tree hash must equal the candidate-commit materialization before and after every rung.

### OPS-004 — P0 — A bridge can forge benchmark evidence; missing traces pass E1 and T1

- **Evidence / state:** The command adapter is hard-coded `benchmark_reportable=True` (`eval_harness/src/opti_eval/adapters/command.py:15-20`) and accepts bridge-written status/reward/verifier JSON (`:122-162`; `eval_harness/src/opti_eval/models.py:49-80`). Summary reportability relies on adapter class plus the absence of an explicit non-reportable marker (`eval_harness/src/opti_eval/summary.py:21-29`). Eligibility compares configured admission strings, silently skips absent or malformed traces (`loop_harness/src/opti_loop/eligibility.py:74-118,121-155`), then returns benchmark eligibility. E1 records `pass` while its dynamic trace audit says pending (`gates.py:122-133`). The shipped benchmark-advancement test's bridge emits no trace (`loop_harness/tests/test_e2e_loop.py:34-49`) yet the test asserts `(accepted, benchmark)` advances state (`:131-152`). **Implementation state: verified false-acceptance path.**
- **Confidence:** High.
- **Reachable causal path:** Hostile candidate/bridge writes all-pass `bridge-result.json` -> declares no `metadata.benchmark_reportable=false` -> configured verifier ID/checksum happens to match a prior admission, but no code proves that verifier executed -> candidate omits trace so T1 has nothing to flag -> E1 passes pending -> E5 produces benchmark evidence -> typed verdict advances state.
- **Consequence:** Reachable false acceptance and forged final state/verifier/activation evidence.
- **Smallest fix:** Candidate runtime must never own the trusted result path. After it exits, a pinned trusted verifier runs separately over read-only state and a required conforming trace. Bind task ID, run ID, base/candidate SHA, execution-tree hash, trace/artifact hashes, verifier binary hash, admission, and reset/environment identity in a signed or owner-written receipt. Missing/malformed trace, unavailable T1, or absent dynamic activation is `invalid`.
- **Acceptance test:** Candidate attempts to write a pass result; missing trace; malformed trace; stale/mismatched verifier; result/trace/task/run hash mismatch; no activation event. Every case must be non-benchmark and unable to advance. A complete trusted-verifier path is the only positive case.

### OPS-005 — P0 — Live-site and destructive side effects are not technically blocked

- **Evidence / state:** ADR-0006 is Open and requires that no live-site task run before policy approval (`docs/adr/0006-live-site-testing-policy.md:1-30`). PROGRAM repeats the prohibition (`PROGRAM.md:56`), but the CLI accepts any command bridge (`loop_harness/src/opti_loop/cli.py:47-53,86-99`) and the adapter has unrestricted shell/network authority. The designated destructive-action middleware is empty at seed (`harness/components/middleware/component.json:1-10`). There is no authorization artifact, destination/action allowlist, account/profile isolation, teardown, or emergency-stop command. **Implementation state: documented-only.**
- **Confidence:** High. Default fixture use reduces accidents but is not an interlock.
- **Reachable causal path:** Operator or compromised config selects a command bridge -> candidate/page prompt causes arbitrary network/browser action -> no ADR-status or owner-authorization check occurs before transport -> externally visible/destructive action happens under inherited account credentials.
- **Consequence:** Uncontrolled external side effect and credential/account exposure while the binding policy remains unresolved.
- **Smallest fix:** Until ADR-0006 is accepted, enforce a hard conductor-side deny for live destinations and deny candidate egress. Later, use a trusted action broker keyed to immutable owner authorization, task/account/action allowlists, isolated profile, and teardown receipt; never delegate the interlock to optimizer-editable middleware.
- **Acceptance test:** A malicious candidate, page injection, custom bridge, and direct CLI attempt each request a canary live/destructive action. All must be blocked before network transport while policy/authorization is absent; owner stop must terminate the entire sandbox.

### OPS-006 — P1 — The claimed atomic acceptance transaction is split-brain and non-recoverable

- **Evidence / state:** Binding ADR-0015 calls gate -> attribute -> record -> accept/reset one atomic transaction (`docs/adr/0015-auto-research-loop-architecture.md:53-60`). Source performs R1-R13 separately (`loop_harness/src/opti_loop/conductor.py:188-299`). Existing eval directories make retry fail (`evaluate.py:99-107`; `eval_harness/src/opti_eval/runner.py:63-70`). Store replacement is not power-loss durable (`store.py:46-65`). **Implementation state: contradicted.**
- **Confidence:** High; exact write map above.
- **Reachable causal path:** Crash after any rung/report/cluster/ledger/learnings/ref write -> pending state and already-created directories remain -> retry fails -> report/ledger/ref/state can each describe different accepted bases with no recovery command.
- **Consequence:** Prevents deterministic recovery and exactly-once acceptance; can lose a campaign or make the wrong base authoritative.
- **Smallest fix:** Add a per-iteration UUID and compact durable journal/state machine (`starting`, `ready`, `evaluating`, `prepared`, `ref-advanced`, `committed`, `cleanup-pending`). Stage artifacts under the UUID, fsync, validate hashes/completion, atomically publish one commit receipt, update the ref with expected-old CAS, and derive/reconcile state/ledger from that receipt. This is a single-host journal, not a distributed transaction platform.
- **Acceptance test:** Deterministic failpoints/kill after every S1-S9 and R1-R13 write, plus ENOSPC/EIO/ref failure/reboot simulation. Restart must converge to exactly one committed or explicitly aborted iteration with one ledger/learning record and a consistent ref/state/receipt.

### OPS-007 — P1 — Concurrent starts and runs can destroy or duplicate work

- **Evidence / state:** `start` checks only a stale in-memory `pending_iteration` (`conductor.py:87-92`), then `worktree_add` force-removes the common path if it exists (`gitutil.py:88-98`). Whole state objects are replaced without a lock (`campaign.py:81-97`). `run_iteration` reads the same pending N and appends without a transaction ID; accepted ref update has no expected-old SHA (`gitutil.py:108-110`). No lock/lease implementation exists. Per-source concurrency is still a deferred requirement (`docs/adr/0005-experiment-gating.md:48-53`; ADR-0015 `:108-113`). **Implementation state: missing.**
- **Confidence:** High.
- **Reachable causal path:** Two `start`s both see no pending -> each targets/removes the same worktree and writes iter-N state/eval paths -> one destroys the other's worktree or overwrites stale state. Two E0-fast `run-iteration`s both append ledger/learnings and clear state. Different campaigns share Docker/site/profile/reset resources and can bias one another.
- **Consequence:** Duplicate/selectively repeated iterations, destroyed optimizer work, last-writer state, ref races, and cross-campaign environment contamination.
- **Smallest fix:** Single-host `flock`: one exclusive per-campaign mutation lock covering init/start/noise/run/recover/cleanup and a narrow shared-resource lock for Git worktree administration and each benchmark environment. Use transaction IDs and CAS for dedupe/ref update.
- **Acceptance test:** Barrier-start two `start`s and two `run-iteration`s (E0 rejection and benchmark acceptance); exactly one may mutate. Run two campaigns against one source and prove serialized reset/profile/container use with separate store/ref identities.

### OPS-008 — P1 — “Outside the repo” is not an owner-only trusted store

- **Evidence / state:** `resolve_store_root` only rejects a root under `repo_root` (`loop_harness/src/opti_loop/store.py:33-43`). `TrustedStore` appends raw `campaign_id` (`:71-77`), and the CLI accepts any string (`cli.py:47-58`). Initialization creates directories/touch/append files with ambient ownership/modes and no symlink/UID check (`campaign.py:108-146`; `store.py:46-65`). The candidate worktree sits inside the same campaign directory (`store.py:119-125`). **Implementation state: partially implemented and contradicted.**
- **Confidence:** High; pure path probes escaped the root. Current host's mode-0700 home happens to shield the default path from another user, but then that user also cannot traverse to the nested candidate worktree.
- **Reachable causal path:** Absolute/`..` campaign ID discards/escapes checked root -> init/load writes or reads another directory. Hostile symlink or permissive parent/umask exposes store. Same-UID candidate runtime bypasses modes entirely. Worktree access forces an undocumented exception through the private store.
- **Consequence:** Campaign collision/aliasing, arbitrary file overwrite/read, cross-campaign evidence corruption, and holdout/store exposure.
- **Smallest fix:** Restrict campaign IDs to a short single safe slug; resolve and require the campaign dir to be an immediate child; reject symlink components; create/verify store/campaign 0700 and files 0600 under expected UID. Place optimizer checkout outside the private store and deliver a sanitized read-only packet. Open security-sensitive paths relative to trusted directory descriptors with no-follow semantics where practical.
- **Acceptance test:** Absolute, `..`, `.`, nested, Unicode-confusable, ref-collision, and symlinked IDs fail before writes. Under hostile umask and a real separate UID, store/holdout remain unreadable while only the intended optimizer checkout subtree is writable.

### OPS-009 — P1 — There is no executable unattended campaign loop

- **Evidence / state:** The CLI exposes one-shot commands only (`loop_harness/src/opti_loop/cli.py:45-67`). `start` only prints instructions/path (`conductor.py:154-164`); no optimizer launcher or completion watcher exists. CLI `init --adapter command` exposes no verifier ID/checksum, timeout, exact model snapshot, or validated campaign-config input (`cli.py:47-53,86-99`), though eligibility requires ID/checksum (`eligibility.py:74-82`). Tests bypass CLI with direct Python overrides (`loop_harness/tests/test_e2e_loop.py:88-128`). Learnings are appended as placeholders, and the next start merely warns (`conductor.py:93-96,334-341`) even though PROGRAM requires learning before retry (`PROGRAM.md:37-39,57-61`). **Implementation state: simulated-only/operator-driven.**
- **Confidence:** High; literal 25-iteration walkthrough above.
- **Reachable causal path:** Operator manually initializes/noise/starts -> manually constructs a separate user/session and delivers inaccessible packet -> manually decides commit is ready -> manually invokes run -> repairs learning/report/push -> manually decides next. No process persists enough state to drive the next transition.
- **Consequence:** Safe activation and 25 unattended iterations are impossible; human orchestration and repair are undisclosed operational dependencies.
- **Smallest fix:** Add one validated campaign-config input and a small persisted driver that checks preflight/lifecycle, launches the existing sandboxed optimizer job, waits on a receipt/deadline, calls the journaled transaction, reports, and loops only while state is `running`. Route validated learning content through the handoff and block same-fingerprint retry before evaluation if absent.
- **Acceptance test:** From CLI only, a disposable 25-iteration fixture campaign launches fake optimizers, resumes after driver kill/reboot, records learning, reports, and reaches a declared terminal state without manual filesystem/config edits.

### OPS-010 — P1 — Stops, budgets, resource limits, and child cleanup are non-preventative

- **Evidence / state:** Runbook promises per-iteration/campaign spend, 10-nonacceptance pause, plateau stop, owner stop, summaries, and final report (`docs/BRINGUP_RUNBOOK.md:154-170`). Campaign config/state has no lifecycle, budget, spend, deadline, owner-stop, or report fields (`loop_harness/src/opti_loop/campaign.py:23-50,123-134`). The only enforcement is `subprocess.run(... timeout=...)` on the immediate shell (`eval_harness/src/opti_eval/adapters/command.py:76-101`), without new session/cgroup/kill-all; captured output is unbounded. Cleanup removes Git files and ignores failure (`gitutil.py:96-98`). **Implementation state: documented-only.**
- **Confidence:** High.
- **Reachable causal path:** Candidate backgrounds children or floods stdout/disk -> shell exits or times out while descendants survive -> no PID/cgroup/storage/cost meter trips -> operator can call `start` after 10 failures, $500, plateau, or owner stop because no state rejects it.
- **Consequence:** Runaway spend/CPU/memory/disk/processes, cross-run interference, unauthorized continuation, and unrecoverable host pressure.
- **Smallest fix:** Persist `running|paused|stopped` plus reason, owner-stop token, task/iteration/campaign deadlines and cost/token counters. Check them before every expensive transition. Run each job in a cgroup/new process group with bounded logs/scratch, CPU/memory/PIDs/disk, TERM/KILL-and-wait for all descendants, and cleanup receipt. Refuse the next transition on missing meter data.
- **Acceptance test:** Owner stop, zero remaining money/tokens/time, 10 failures, two plateau windows, CPU/memory/PID/disk/output flood, browser hang, auth expiry, and a SIGTERM-ignoring grandchild each prevent continuation and leave no process/profile/container behind.

### OPS-011 — P1 — Transfer is identity-unbound and cannot pause the campaign

- **Evidence / state:** The plan contains campaign name, accepted iteration numbers, cadence, prose measures, and panel only (`loop_harness/src/opti_loop/transfer.py:28-64`). Evaluation accepts any `model -> float` dictionary without campaign/checkpoint/base/accepted SHA, task set, model snapshot, repeats, uncertainty, artifact hash, or panel completeness (`transfer.py:67-85`). CLI does not load a campaign for `transfer-eval`, always returns 0, and persists nothing (`cli.py:66-84`). **Implementation state: simulated-only/contradicted.**
- **Confidence:** High; safe probes observed rejected transfer exit 0 and one-model NaN become `transfer_supported`.
- **Reachable causal path:** Caller supplies fabricated, partial, stale, or non-finite deltas -> median function returns transient support/reject JSON -> no checkpoint identity is validated -> even rejection changes no state -> `start` remains permitted. If no changes are accepted, cadence never fires and no fallback exists.
- **Consequence:** The transfer bet can be falsely supported, a failed criterion cannot halt work, and campaigns can run indefinitely without a checkpoint.
- **Smallest fix:** Persist an immutable checkpoint object bound to campaign, base and accepted SHA, run identity, exact transfer task set, discovery exclusion, panel model snapshots, repeats, uncertainty, costs, and artifact hashes. Validate finite complete inputs. A rejected committed checkpoint atomically sets campaign `paused`, and `start` refuses it. Add a no-acceptance/elapsed-iteration fallback cadence.
- **Acceptance test:** Reject NaN/Inf, missing panel member, stale SHA/task set/model, missing repeats/uncertainty, duplicate checkpoint, and fabricated artifact hash. A valid negative checkpoint must return nonzero, persist rejection, and block `start` until an explicit owner resolution.

### OPS-012 — P2 — Evidence completeness, identity, and upgrade compatibility are under-bound

- **Evidence / state:** `_run_identity` hashes suite names, adapter/config/fixed variables, and catalog bytes, but not suite manifest/task-set bytes, thresholds, eval/gate code, bridge/verifier binary receipt, admissions, environment/reset/container image, judge prompt, or evidence artifacts (`loop_harness/src/opti_loop/conductor.py:60-71`). `load_run` trusts summary/results without checking `run.json.status`, expected task IDs/count, duplicates, hashes, or suite identity (`evaluate.py:111-133`). Strict comparison does not enforce coverage/task-set equality (`compare.py:75-103`). Config/state load has no schema validation/migration (`campaign.py:149-164`). **Implementation state: incomplete.**
- **Confidence:** High.
- **Reachable causal path:** Crash/attacker/upgrade leaves a completed-looking summary plus truncated or altered results -> `load_run` constructs a shorter run -> strict comparison uses the valid intersection and supplied summary validity -> stale noise/evidence survives relevant code/suite/environment changes -> acceptance/reporting proceeds or crashes inconsistently.
- **Consequence:** Stale, partial, corrupt, or attacker-modified evidence can be reused; campaign resume after upgrades is not deterministic.
- **Smallest fix:** Define one run receipt with expected task IDs, completed status, base/candidate/execution-tree SHA, suite/catalog/threshold/config/bridge/verifier/environment hashes, artifact hashes, and schema/code version. Validate before load/reuse; stage incomplete tasks and resume only receipt-validated units. Require explicit migration or safe refusal on schema changes.
- **Acceptance test:** Delete/duplicate/reorder a task, truncate results, leave `run.json` running, alter summary/artifact/suite/verifier/environment hash, and load old state under new code. Every mismatch must be detected before comparison; a supported migration must be explicit and reproducible.

### OPS-013 — P2 — Status and reporting cannot reveal split-brain, stalls, or cleanup failure

- **Evidence / state:** `status` parses the whole ledger and echoes state, ledger count, noise band, and last five verdicts only (`loop_harness/src/opti_loop/cli.py:119-134`). It does not resolve the accepted Git ref, hash reports/artifacts, inspect pending age/PID/lease, worktree/process/browser/container existence, quarantine, transfer due/failure, auth/environment drift, spend, disk, publication state, or cleanup. A corrupt ledger line raises. Worktree removal failures are suppressed (`gitutil.py:96-98`). Reporting/push is prose (`docs/BRINGUP_RUNBOOK.md:166-170`). **Implementation state: missing.**
- **Confidence:** High.
- **Reachable causal path:** Crash creates ref/state/ledger split or orphan child -> operator runs status -> output looks like ordinary stale state or crashes on JSON -> no alert/exit code identifies the unsafe condition -> next manual action compounds it.
- **Consequence:** Split-brain, stalled/orphaned work, repeated invalid runs, runaway cost/storage, quarantine anomalies, and failed cleanup/transfer can remain invisible.
- **Smallest fix:** Make `status` a read-only reconciler/doctor: validate journal/receipt/ref/state/ledger/report hashes, pending age/heartbeat/PID/cgroup/worktree/cleanup, quarantine, transfer/publication state, disk/budget, and non-secret auth/environment fingerprint. Return nonzero with a single actionable repair state; add bounded retained audit metadata.
- **Acceptance test:** Inject each split/ref mismatch, stale pending lease, dead/live orphan, corrupt tail, missing report, quarantine backlog, disk/cost breach, auth drift, failed transfer/push, and cleanup error. `status` must identify each without exposing holdout content or secrets.

### OPS-014 — P3 — Operator instructions and status claims contradict the executable interface

- **Evidence / state:** Generated packet tells the optimizer to put `manifest.json` in the trusted iteration directory and run nonexistent `opti-loop gate` (`loop_harness/src/opti_loop/packet.py:84-88`); conductor actually reads worktree-root manifest (`conductor.py:188-196`) and CLI exposes `run-iteration`. PROGRAM and CLI docstring show `--store-root` after the subcommand (`PROGRAM.md:73-83`; `cli.py:1-14`), but parser defines it globally (`cli.py:41-58`). Root README says ADR-0004/0005 and judge/gate/trace decisions remain open (`README.md:23-25,73-80`), contradicting the decision register (`docs/DECISION_REGISTER.md:16-18,27-29`); handoff later calls accepted items unresolved (`docs/AGENT_HANDOFF.md:37-48,58-66`). **Implementation state: contradicted documentation.**
- **Confidence:** High; CLI negative probes reproduced both command defects.
- **Reachable causal path:** Optimizer follows generated packet -> cannot write owner-only iteration directory or invokes nonexistent command -> human repairs handoff. Operator follows documented flag order -> parser rejects. Reviewer/operator follows stale status -> applies wrong activation assumptions.
- **Consequence:** Manual repair, misleading readiness, and brittle automation; nonblocking only because stronger P0/P1 blockers already prohibit activation.
- **Smallest fix:** Correct packet/path/command/flag order and stale decision text immediately. Add narrow parser/documentation tests that execute every documented command form and compare status claims to `DECISION_REGISTER.md`.
- **Acceptance test:** Generate a packet, run every command exactly as printed in a disposable campaign, and assert no nonexistent command/path. Documentation verifier must fail on decision-status contradictions.

## 8. High-risk hypothesis disposition

| # | Hypothesis | Disposition | Basis |
|---:|---|---|---|
| 1 | Candidate code executes with conductor credentials/store access despite editor confinement | **HELD** | Command path is executable today and same-UID/full-env; real browser bridge itself is not implemented. |
| 2 | “Outside the repo” is treated as sufficient store security | **HELD** | Code checks location only; owner, mode, campaign child, symlink, and execution-principal separation are absent. |
| 3 | Acceptance can split across report, ledger, Git ref, and state after crash | **HELD** | R6-R12 are independent writes with no journal/recovery. |
| 4 | Concurrent commands can duplicate/overwrite an iteration | **HELD** | No lock/CAS/transaction ID; stale pending checks and one shared worktree/path. |
| 5 | JSONL append/file replacement provides weaker durability than claimed | **HELD** | No fsync chain/lock/tail recovery; many trusted files are direct rewrites. |
| 6 | Incomplete/corrupt evidence can be resumed or reused as complete | **HELD** | Missing trace becomes benchmark; run load ignores completion/task-set/hash receipts. |
| 7 | Surviving child processes/shared browser state influence later runs | **HELD** | Shell timeout has no process-group/cgroup cleanup; profiles/environments are unowned. |
| 8 | The loop requires a human to launch or repair each iteration | **HELD** | No optimizer launcher/outer driver; 25-iteration path requires manual S/O/R and learning/report work. |
| 9 | Stops and budgets report violations but do not prevent continuation | **HELD** | Most are not even computed/reported; no lifecycle/budget gate exists. |
| 10 | Transfer accepts identity-unbound inputs or cannot pause the campaign | **HELD** | Stateless arbitrary floats, including NaN; no campaign argument/state mutation. |
| 11 | Candidate/child processes inherit unnecessary secrets | **HELD** | `os.environ.copy()`, same home/UID, raw logs, judge/probe shells. |
| 12 | Live-site execution is possible while ADR-0006 remains unresolved | **HELD** | Arbitrary command + unrestricted network; no policy/authorization interlock. |
| 13 | CLI/runbook/packet claims atomic or autonomous behavior that is only prose | **HELD** | Sequential R1-R13; one-shot CLI; impossible packet instructions. |
| 14 | No signal reliably exposes split-brain, stalled work, runaway cost, or failed cleanup | **HELD** | `status` does not reconcile any of those conditions. |

## 9. Minimum fault/security tests required before activation

These tests are blockers, not optional hardening:

1. **Trusted Git boundary:** real optimizer UID attempts replace refs, grafts, hooks/config/includes, common refs, object/admin writes, forbidden commit, two commits, empty commit, ignored payload, and post-E0 mutation. Evaluation must use only an owner-materialized immutable candidate.
2. **Sandbox escape and secret canaries:** hostile candidate probes env/home/key files, store/admissions/quarantine/holdout, main repo/Git, `/proc`, Docker, browser profiles, arbitrary filesystem, IPC/signals, DNS/network, and model endpoints. Deny everything not explicitly required; canary values must not appear in stdout/stderr/errors/traces/screenshots/artifacts/judge input/export.
3. **Trusted verifier/evidence:** candidate-forged result, missing/malformed/truncated trace, missing activation, stale task/run/candidate hash, wrong verifier binary/checksum/admission, artifact-path escape, duplicate/missing task. All fail closed; only owner-written receipt passes.
4. **Process/resource cleanup:** child/grandchild daemonizes, ignores TERM, holds worktree/profile/socket, floods stdout, consumes CPU/memory/PIDs/disk, and hangs browser/network. Deadline must kill/wait for the whole cgroup and prove zero survivors before unlock.
5. **Start/accept fault matrix:** kill after every S1-S9 and R1-R13 mutation. Include disk full, permission loss, EIO, corrupt JSON/JSONL tail, failed replace/fsync/ref/CAS, reboot, auth expiry, network loss, browser/verifier/judge failure. Recovery must converge deterministically.
6. **Concurrency:** barrier two init/start/noise/run/recover calls for one campaign and overlapping campaigns on one environment. Exactly one same-campaign mutation; source reset/profile/container access serialized; no cross-campaign collision.
7. **Namespace/permissions:** absolute, traversal, nested, dot, confusable, symlink, ref-prefix-collision IDs; hostile umask; separate optimizer UID. No path escapes; store/holdout 0700/0600 and inaccessible; worktree remains usable through the explicit broker only.
8. **Evidence durability/tamper:** alter every state/report/ledger/learning/cluster/quarantine/corpus/eval/artifact/ref link, truncate each file, delete candidate object, and replay duplicate transaction. Doctor detects it; no acceptance or silent repair without receipt.
9. **Preventative controls:** owner stop, zero and near-limit tokens/money/time, 10 nonacceptances, plateau windows, campaign ceiling, missing meter data, disk quota. No expensive process launches after a pause/stop.
10. **Transfer:** finite full panel bound to accepted/base SHA, task set, model snapshots, repeats, uncertainty, and hashes. Reject NaN/Inf/partial/stale/fabricated inputs; negative result persists pause and blocks start. Test no-acceptance fallback cadence.
11. **Live-site deny:** malicious command/page/candidate attempts a canary live/destructive request before policy and owner authorization. It must be blocked before transport and logged without secret/page leakage.
12. **Unattended rehearsal:** 25 fixture iterations through the real CLI/driver with injected driver kill, optimizer timeout, task crash, auth drift, rejected transfer, and report/push failure. No human repair except explicit T3 decisions; every terminal state is visible and resumable.
13. **Upgrade resume:** open old config/state/journal/run receipts with new code/schema. Require explicit migration with preserved hashes or safe refusal.

## 10. Dependency-ordered YAGNI remediation path

1. **Keep real/live activation hard-disabled.** Correct the strongest false claims and packet commands now so nobody mistakes fixture success for readiness.
2. **Close the hostile-code boundary first.** Replace the linked trusted worktree with a standalone optimizer checkout/import broker; run candidate tasks in one minimal single-host sandbox/cgroup with a clean environment, private scratch, no trusted mounts/Docker/home, and default-deny network.
3. **Move scoring behind the boundary.** A trusted wrapper invokes the pinned verifier after candidate exit, requires a conforming activation/T1 trace, and writes one hash-bound run receipt. Candidate-supplied results are evidence, never authority.
4. **Make store identity real.** Safe campaign slug, path/symlink containment, owner/mode assertions, worktree outside store, per-campaign/resource locks.
5. **Journal the existing state machine.** Stable iteration UUID, immutable staged artifacts, fsync + commit receipt, ledger dedupe, expected-old ref CAS, deterministic `recover/doctor`. Avoid a database/distributed platform; a locked append-only journal and atomic receipt are sufficient for a single host.
6. **Add preventative lifecycle control.** Minimal `running|paused|stopped`, owner stop, deadlines/resource/cost meters, cleanup receipt, and one driver that advances only after checks.
7. **Bind transfer and publication.** Immutable checkpoint identity, finite complete input validation, failed-transfer pause, no-acceptance fallback, and `publication_pending` for push/report failures.
8. **Expose health and prove it.** Reconciliating status plus the fault/security/25-iteration suite above. Only then revisit activation authorization.

## 11. Cross-part handoff

Interface questions only; this report does not re-audit Part 1 environment selection or Part 2 statistics:

1. **Part 1:** Which exact bridge, native-verifier, reset/environment, container/image, browser-profile, and task-set hashes must the operations receipt pin for each source family?
2. **Part 1:** Can every selected real bridge place candidate execution behind a trusted verifier without giving the candidate the result path, credentials, Docker socket, or environment-reset authority?
3. **Part 2:** What minimum complete trace/activation/T1 event set and artifact binding must make a run statistically eligible, so operations can fail closed on missing evidence?
4. **Part 2:** What exact transfer checkpoint payload (task exclusions, repeats, uncertainty, model panel/snapshots, decision rule) must operations bind before a failed criterion pauses the campaign?
5. **Part 2:** Which plateau/nonacceptance signals and measured budget counters are decision inputs versus diagnostics, so the conductor can enforce them without silently inventing statistical thresholds?

## 12. Direct answers

- **Can candidate code access secrets or forge trusted evidence?** **Yes on the executable command path.** It inherits conductor authority and receives trusted result/output paths. It can also defeat editing-time E0 through shared Git administration or unbound runtime bytes.
- **Can acceptance commit exactly once across all trusted records?** **No.** Report, manifest, cluster register, ledger, learnings, ref, state, and cleanup are independent, unlocked writes.
- **Can every state-transition crash recover safely?** **No.** Existing rung directories block retry, and no journal/recovery command reconciles later split-brain.
- **Can concurrent commands corrupt work?** **Yes.** Same-campaign commands race one worktree/state/ledger; different campaigns share ungoverned environments/resources.
- **Are stops and budgets preventative?** **No.** They are prose except an immediate-shell timeout, which does not kill descendants or prevent the next iteration.
- **Does failed transfer actually halt the campaign?** **No.** Transfer is stateless, identity-unbound, accepts non-finite/partial inputs, returns exit 0, and never changes campaign state.
- **Is live-site use blocked pending policy/authorization?** **No.** Default fixture behavior is safe-by-default, but arbitrary network-capable command bridges are technically available with no interlock.
- **Can 25 iterations run without undisclosed human orchestration?** **No.** Each requires manual start, optimizer launch/handoff, run, learning/report decisions, and next-step invocation.
- **What minimum blocker set changes this part's verdict?** (1) isolated immutable candidate edit/runtime plus trusted verifier/required trace; (2) safe store namespace/permissions and locked journaled exactly-once acceptance/recovery; (3) preventative lifecycle/budget/process cleanup; (4) identity-bound transfer/live-site authorization that persists pause; and (5) passing the minimum fault/security and 25-iteration rehearsal suite.

> **OPERATIONS SAFE FOR AN UNATTENDED REAL CAMPAIGN: NO**

Shortest dependency-ordered blockers:

1. Remove optimizer/candidate access to trusted Git, secrets, store, verifier authority, Docker, and unrestricted network; require trace-backed trusted verification.
2. Replace the claimed multi-file “atomic” function with locked, journaled, receipt-bound, CAS-updated, recoverable acceptance.
3. Implement preventative stop/budget/process cleanup and a persisted unattended driver.
4. Bind transfer/live-site/publication decisions to immutable campaign state and make failures pause.
5. Pass the listed hostile-code, crash, concurrency, durability, and 25-iteration tests before owner activation.
