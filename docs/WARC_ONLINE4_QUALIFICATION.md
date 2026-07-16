# WARC-Bench `online.4` qualification

Status: reversible milestone-F software qualification candidate. The initial
reviews and subsequent targeted rereviews returned FIX; the additional bounded
correction is implemented and locally verified, and targeted final correctness/
elegance rereviews remain pending. No live
run has been performed, no fixture output is benchmark evidence, and ADR-0003
remains Open.

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

`mode` is `production` or `local_fixture`. Production is potentially
reportable only after the existing AR-003 admission path accepts the complete
run; `local_fixture` is always `benchmark_reportable=false`, uses evidence
class `local_fixture`, and cannot advance accepted state.

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

Keep the production config and every secret outside the repository. First run
the non-executing preflight:

```bash
opti-loop --repo-root /path/to/opti-browser-tool \
  warc-online4-preflight --config /owner-only/warc-online4.json
```

A successful response explicitly says `lifecycle_executed: false`. Then
initialize the one-task qualification campaign:

```bash
opti-loop --repo-root /path/to/opti-browser-tool \
  --store-root /owner-only/opti-store \
  init --campaign warc-online4-qualification \
  --adapter warc-online4 \
  --warc-config /owner-only/warc-online4.json \
  --dev-suite warc-online4-qualification
```

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

These commands do not authorize a live run. Do not execute `start` until the
owner has supplied every input below and separately authorized the exact
qualification.

## Current blockers

- exact WACZ bytes and SHA-256;
- exact native JavaScript verifier bytes/SHA-256 and completed admission
  evidence;
- pinned WARC handler/manifest/replay files, resolved BrowserGym environment,
  Gymnasium, Playwright facade/driver, browser binary/revision, Python, Node,
  and bubblewrap files with version
  outputs/checksums;
- exact production executor provider/model/settings/tool
  schema and required credential environment variables;
- provenance origins, license ID, acknowledged license evidence, retention
  policy, and permission to retain the resulting artifacts;
- deployed separate conductor/optimizer UIDs, static inbox ownership, and
  verified single-host network/filesystem confinement;
- real reset/oracle/verifier probes, task calibration, runtime/noise evidence,
  and milestone-E decision calibration;
- explicit owner authorization for any live, paid, or externally sourced run.

The deterministic test fake creates none of these claims. It substitutes only
the replay, BrowserGym, and executor primitives while traversing the same
repository-owned treatment-load, reset, action, verifier, final-state, trace,
artifact, cleanup, and activation lifecycle under temporary local files.
