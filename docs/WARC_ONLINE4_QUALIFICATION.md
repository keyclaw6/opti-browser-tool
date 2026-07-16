# WARC-Bench `online.4` qualification

Status: reversible milestone-F software qualification checkpoint. Its bounded
software qualification was independently reviewed and committed at `7c245e5`;
the final Sentinel readiness correction is committed at
`04ca532b078d31a1ad0959c7bcf94302e7362abb` by writer session
`019f6bf0-e541-7952-9cb2-4aa547786a35`. Correctness reviewer session
`019f6bf7-deca-79a0-96b1-57c1df08e0b6` and elegance/YAGNI/vision reviewer
session `019f6bf7-df19-7070-b594-7c421a0e956c` both returned CLEAN on frozen
production/test digest
`f53db249a45600168a45392efdd800cdb209dbf799798125f705b98ab05f2d75`.
This remains a software checkpoint, not live qualification: no live operation,
external spend, merge, push, reportability claim, or campaign authorization has
occurred, and ADR-0003 remains Open. `benchmark_reportable=false` and
`benchmark_evidence=false` remain binding.

## What exists

`warc-online4` is the only source-specific qualification adapter. It accepts only
catalog task `warc-bench-online-4` / native task `online.4` at WARC-Bench commit
`98d213ccd2b4380761738e1d144467a8695e37c5`, manifest Git blob
`6b2bc7ee04b3231325fe3a84b195d26d0c589287`, and WACZ locator
`environments/web_archives/alaska_airlines/alaska_airlines_flight_booking.wacz`.
It does not dispatch other WARC tasks and does not make the generic command or
registry adapters reportable. Production-mode output is only a proposal to the
existing admission path; this software slice establishes no reportability.

The adapter preflights all external identities and the exact positive verifier
admission before task execution. A repository-owned launcher owns BrowserGym/
WARC reset/action/state/close, model request construction, treatment loading,
evidence capture, deadlines, and cleanup over pinned standard boundaries. It
invokes the exact admitted JavaScript matcher on the same live Playwright page
after reset and after the final action, before cleanup, and returns the existing `EvalRun` / AR-003 result,
trace, final-state, and artifact shapes.

The conductor reuses D3 activation evidence to bind the exact materialized
build and changed treatment path. Its authority is the repository-owned
lifecycle trace plus the task trace and run record. An external boundary echo
or candidate telemetry is insufficient. There is no parallel activation
receipt.

## Closed configuration

The JSON document is strict, closed, and `schema_version: "0.1.0"`. It has
exactly these top-level fields:

```text
schema_version, mode, task, source, wacz, verifier, provenance, runtime,
executor, credentials, confinement, limits, treatment_path, protocol_identity
```

`mode` is `production` or `local_fixture`. Production is potentially eligible
only after execution and the existing AR-003 admission path accepts the
complete run. Source preflight always emits `benchmark_reportable=false`
because it executes no task lifecycle and admits no run; its separately named
`potential_benchmark_eligibility` fact is not reportability.
`local_fixture` is always `benchmark_reportable=false`, uses evidence class
`local_fixture`, and cannot advance accepted state.

Required values are:

- `task`: exactly `warc-bench-online-4`, `warc_bench`, `online.4`;
- `source`: the exact commit, manifest path/blob, and WACZ locator above;
- `wacz`: absolute regular non-symlink path, owner-computed SHA-256, and the
  exact pinned replayed page URL
  `https://www.alaskaair.com/search/?A=1&C=0&L=0&O=JFK&D=SFO&OD=2025-02-18&DD=2025-02-18&RT=true&errorRedirect=true`;
- `verifier`: exact verifier ID, absolute native-JavaScript path/SHA-256, and
  exact admitted-verifier JSONL path/SHA-256. The shared strict admissions
  authority requires a positive row for exactly this ID, task, and checksum;
- `provenance`: WACZ/verifier origins, license ID, absolute license-evidence
  path/SHA-256, and explicit `acknowledged: true`;
- `runtime`: exact `python`, `node`, loaded WARC-Bench handler module, WARC
  replay `dist/index.js`, the Gymnasium-resolved `online.4` environment module,
  Gymnasium and Playwright facade modules, Playwright driver, browser,
  bubblewrap, and CDP port identities. Each file identity contains an absolute path,
  file SHA-256, complete side-effect-free version-command argv using another
  pinned runtime executable, and the
  exact combined stdout/stderr expected from it;
- `executor`: provider, route, one exact endpoint-consumed model identifier,
  settings object, and tool-schema SHA-256. The shared frozen protocol's required
  snapshot/revision projections are derived as that same model identifier; they
  are not separately configurable claims;
- `credentials.required_env`: environment-variable names only. Secret values
  never enter config, traces, results, or artifacts;
- `confinement`: `single_host: true`, `network: "loopback-only"`,
  `filesystem: "read-only-except-task-output"`, the distinct optimizer UID,
  and its absolute static-inbox directory. Production rejects a conductor
  running as the optimizer UID or an inbox owned by another UID;
- `limits`: positive integer timeout, deadline, and action budget, with timeout
  no greater than the deadline;
- `treatment_path`: the exact safe candidate-relative file loaded by the
  trusted lifecycle, embedded byte-for-byte in the model policy request, and declared in
  the experiment change scope; and
- `protocol_identity`: the exact WARC source setup/reset/environment/browser
  identities, activation instrumentation identity, lane/config path, and the
  already-required frozen repeated-protocol object. This slice does not choose
  or calibrate milestone-E statistics.

The normal adapter invokes the repository-owned lifecycle directly. The
conductor starts one in-repository source worker with standard bubblewrap
arguments (`--unshare-all`, read-only root, task-output bind, private `/tmp`).
That credential-free worker verifies the files actually loaded for WARC-Bench,
Gymnasium, and Playwright, plus the resolved `online.4` entry-point module and
the Playwright driver bytes. It constructs the pinned
`WebReplayServerSessionHandler` with keyword arguments `task_id="online.4"`,
the exact WACZ, the pinned page URL, and the configured debugging port. Because
this pinned handler revision builds its replay command from `task_config`, the
worker verifies that configuration identifies `online.4` and changes only
`task_config["env"]["data_path"]` and `["start_url"]`; timestamp and all other
fields remain intact. Before that adaptation, it derives the installed
`environments/benchmark.json` from the verified handler module, recomputes its
pinned Git-blob SHA-1, parses its unique `online.4` row, and requires the
handler's original task config to equal that row. The resulting blob/content/
row digests are retained as source-manifest evidence. It then calls
`setup_webreplay_server(run_headless=True)`, checks the handler-co-located
replay `dist/index.js` and pinned Node resolution, and creates exactly
`browsergym/subtaskbench.online.4` with
only `cdp_port` and `connect_via_cdp=True`. It checks the live Playwright browser
executable, then calls standard `env.reset`, `env.step`, and `env.close`, with
handler cleanup in `finally`. No owner-authored replay/BrowserGym/sandbox bridge
protocol is required. CDP and worker confinement are loopback-only; the replayed
page retains the exact pinned HTTPS URL above.

Worker stdout is reserved for the JSON-lines control channel. Before any
upstream setup/reset/step/close code runs, ordinary stdout and stderr file
descriptors are redirected to a bounded discard sink, preventing handler or
replay diagnostics from corrupting IPC or filling the already-piped stderr.

The conductor constructs the fixed MiniMax-M3 request for
`https://opencode.ai/zen/go/v1/messages`, including the exact materialized
candidate bytes in the system policy and the repository-owned constrained
BrowserGym action tools. It hashes the bytes actually passed to the HTTP
transport and stores the credential-free request as cited evidence. The API
credential remains only in the request header. Each HTTP call is interrupted at
the lesser of the configured request timeout and the remaining single lifecycle
deadline across connection and the complete response read; the adapter has no
second deadline clock.
The native verifier runs under
the same standard bubblewrap confinement, and no unpinned runtime path is added.

The launcher records treatment load, applied model-request digest,
replay/reset/actions, live verifier result, final state, and cleanup in a task-local lifecycle trace.
The adapter recomputes its digest, checks the exact candidate-bearing request,
cites it from the AR-003 task trace, and the conductor checks those files again
before E1 passes. An echo or a request that drops/substitutes the candidate is invalid.

While the page is live, the worker reads and re-hashes the admitted verifier,
requires its contents to be the pinned upstream `online.4` matcher, retains the
exact reset-time Playwright `Page`, rejects replacement after any step, evaluates
both initial and final checks on that object, requires reset to return `false`, and records
the final boolean with page URL, projected-state digest, verifier checksum,
upstream commit, and manifest blob. Captured JSON state is supporting evidence,
not scoring authority. Infrastructure/reset/identity/verifier/cleanup failures
are invalid/error evidence, never task failure. Worker reads and cleanup are
deadline-bounded; every failure closes pipes, terminates, then kills and reaps
an uncooperative worker.

## Operator flow after owner-supplied inputs exist

Copy
[`evals/warc-online4.production.template.json`](../evals/warc-online4.production.template.json)
to an owner-only path outside the repository. Replace every `OWNER_*` string
with the named owner-supplied value, preserving JSON types: UID and all values
ending in `_INTEGER` become JSON integers, and values ending in `_NUMBER`
become JSON numbers. Compute every checksum from the exact deployed bytes;
record complete side-effect-free version commands and their exact combined
stdout/stderr. The template includes every source asset, checksum, runtime,
executor, credential-name, confinement, protocol identity, and calibrated
decision field consumed by the closed preflight. It contains no secret value.

Keep the completed production config and every secret outside the repository.
Set `OPENCODE_API_KEY` only in the conductor environment, then run source
preflight against that completed copy:

```bash
opti-loop --repo-root /path/to/opti-browser-tool \
  warc-online4-preflight --config /owner-only/warc-online4.json
```

A successful response explicitly says `lifecycle_executed: false`,
`benchmark_reportable: false`, and
`potential_benchmark_eligibility: true`. Preflight authorizes nothing and runs
no task lifecycle, browser/model campaign, admission, or performance
evaluation. It may run only the configured bounded, side-effect-free version
commands needed to verify runtime identity.

Only after the owner has explicitly authorized this exact production campaign,
initialize it with the existing campaign-owned metering and authorization
inputs (these intentionally are not duplicated into source configuration):

```bash
opti-loop --repo-root /path/to/opti-browser-tool \
  --store-root /owner-only/opti-store \
  init --campaign warc-online4-qualification \
  --adapter warc-online4 \
  --warc-config /owner-only/warc-online4.json \
  --dev-suite warc-online4-qualification \
  --max-iterations OWNER_CHOSEN_INTEGER \
  --max-attempts OWNER_CHOSEN_INTEGER \
  --deadline-seconds OWNER_CHOSEN_INTEGER \
  --external-metering-id OWNER_APPROVED_METER_IDENTITY \
  --authorize-production-campaign
```

`--authorize-production-campaign` records that prior owner decision as
`owner_authorized`; it does not originate authorization. Omitting the flag
retains the missing-authorization blocker, and `start` cannot execute the
production campaign until that blocker is removed.

Start creates the accepted-build baseline through the normal conductor path:

```bash
opti-loop --repo-root /path/to/opti-browser-tool \
  --store-root /owner-only/opti-store \
  start --campaign warc-online4-qualification
```

After the optimizer writes only the frozen candidate surface and supplies the
D3 static bundle and manifest from its separately owned inbox, the owner runs:

```bash
opti-loop --repo-root /path/to/opti-browser-tool \
  --store-root /owner-only/opti-store \
  run-iteration --campaign warc-online4-qualification \
  --candidate-bundle /optimizer-owned/inbox/candidate.bundle \
  --candidate-manifest /optimizer-owned/inbox/manifest.json
```

Preflight and configuration commands do not themselves authorize a live run.
Do not supply `--authorize-production-campaign` or execute `start` until the
owner has supplied every input below and explicitly authorized the exact
qualification. None of these steps establishes benchmark reportability or
performance evidence.

## Current blockers

- owner-supplied WACZ and checksum, with provenance and license evidence;
- native verifier executable identity and checksum with positive admission;
- exact BrowserGym, Playwright, browser/runtime, and model-transport identities;
- credentials only if the selected source requires them;
- optimizer UID, inbox ownership, and runtime confinement;
- real reset, final-state, trace, and artifact evidence;
- real calibration, transfer, and holdout evidence;
- metering and required owner decisions; and
- explicit campaign authorization.

The deterministic test fake creates none of these claims. It substitutes only
the replay, BrowserGym, and executor primitives while traversing the same
repository-owned treatment-load, reset, action, verifier, final-state, trace,
artifact, cleanup, and activation lifecycle under temporary local files.
