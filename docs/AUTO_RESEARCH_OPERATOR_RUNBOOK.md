# Auto-research foreground operator runbook

Status: offline software-readiness workflow only. These commands do not
authorize a live source, browser, model, paid request, or reportable campaign.
Fixtures and simulations are never benchmark evidence.

## Clean install and deterministic proof

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
make install

make install-check
PYTHONPATH=eval_harness/src:judge_harness/src:loop_harness/src \
  OPTI_BROWSER_REPO_ROOT="$PWD" \
  python -m unittest \
  loop_harness.tests.test_e2e_loop.TransactionalLoopTest.test_warc_online4_local_fixture_traverses_real_seam_and_is_state_inert \
  loop_harness.tests.test_e2e_loop.TransactionalLoopTest.test_foreground_lifecycle_pause_resume_and_status_use_existing_transaction \
  loop_harness.tests.test_e2e_loop.TransactionalLoopTest.test_accepted_publication_recovers_every_post_gate_boundary
```

Keep this virtual environment activated for the later `opti-loop` commands.
`make install-check` remains a separate disposable packaging proof; it does not
install the CLI into the activated environment.

The deterministic WARC fake traverses the repository-owned WARC boundary,
D3 Git materialization/activation, the repeated E decision, terminal recording,
LearningRecord creation, and interruption recovery. It creates no WACZ,
verifier, runtime, credential, calibration, performance, or reportability
claim.

## Initialize and operate the offline fake

Choose an owner-only store outside the repository and explicit closed limits:

```bash
STORE=/absolute/owner-only/opti-store
CAMPAIGN=offline-rehearsal

opti-loop --repo-root "$PWD" --store-root "$STORE" init \
  --campaign "$CAMPAIGN" \
  --adapter harness-fixture \
  --harness-file harness/components/policy/quality.txt \
  --max-iterations 3 \
  --max-attempts 6 \
  --deadline-seconds 3600

opti-loop --repo-root "$PWD" --store-root "$STORE" \
  preflight --campaign "$CAMPAIGN"
opti-loop --repo-root "$PWD" --store-root "$STORE" \
  run --campaign "$CAMPAIGN"
opti-loop --repo-root "$PWD" --store-root "$STORE" \
  status --campaign "$CAMPAIGN"
```

`run` opens one iteration when idle. Edit only the printed frozen allowlist in
the printed candidate worktree, create exactly one commit and `manifest.json`,
then invoke `run` again. It resumes the pending iteration or accepted-
publication receipt instead of creating another iteration.

Pause and stop are preventative foreground safe-boundary requests:

```bash
opti-loop --repo-root "$PWD" --store-root "$STORE" pause --campaign "$CAMPAIGN"
opti-loop --repo-root "$PWD" --store-root "$STORE" resume --campaign "$CAMPAIGN"
opti-loop --repo-root "$PWD" --store-root "$STORE" stop --campaign "$CAMPAIGN"
```

`resume` clears a paused or stopped request and advances one safe foreground
step. There is no daemon or cross-process supervisor.
`start` and `run-iteration` remain the explicit lower-level equivalents.

`status` is read-only. It reports lifecycle request/state, campaign state versus
the accepted Git ref, pending iteration/publication recovery, the last ledger
decision and publication receipt, latest validated LearningRecord, WARC
preflight state, limit/deadline blockers, and cleanup health. It prints required
credential variable names only, never values or private holdout contents.

## Later authorized WARC `online.4` qualification

Keep the production config and secrets outside the repository. First run the
non-executing source preflight:

```bash
opti-loop --repo-root "$PWD" \
  warc-online4-preflight --config /owner-only/warc-online4.json
```

Only after every checklist item below is satisfied and the owner explicitly
authorizes this exact campaign may it be initialized:

```bash
opti-loop --repo-root "$PWD" --store-root /owner-only/opti-store init \
  --campaign warc-online4-qualification \
  --adapter warc-online4 \
  --warc-config /owner-only/warc-online4.json \
  --dev-suite warc-online4-qualification \
  --max-iterations OWNER_CHOSEN_INTEGER \
  --max-attempts OWNER_CHOSEN_INTEGER \
  --deadline-seconds OWNER_CHOSEN_INTEGER \
  --external-metering-id OWNER_APPROVED_METER_IDENTITY \
  --authorize-production-campaign

opti-loop --repo-root "$PWD" --store-root /owner-only/opti-store \
  preflight --campaign warc-online4-qualification
```

Production advancement remains blocked when `--external-metering-id` is absent.
This identifier names an owner-approved real meter; it does not invent prices,
token counts, or calibration.

Exact activation checklist:

- owner-supplied WACZ bytes, provenance, license/retention permission, and
  SHA-256;
- exact native JavaScript verifier, checksum, and positive admitted-verifier
  evidence;
- pinned Python, Node, WARC manifest/handler/replay, resolved Gym environment,
  Playwright facade/driver, browser, and bubblewrap identities/checksums;
- exact provider route, endpoint-consumed model identity/settings, credential
  variable names and available authentication, plus an approved external
  spend/token meter;
- distinct conductor/optimizer UIDs, optimizer-owned static inbox, frozen
  writable allowlist, and verified single-host loopback/read-only confinement;
- calibrated repeated protocol values, real reset/oracle/probe evidence,
  noise/difficulty evidence, and a closed scheduled-transfer result when due;
- explicit owner authorization for the exact live/paid campaign.

Missing any item is a blocker, not a fixture substitution. ADR-0003 remains
open; CommandAdapter remains non-reportable; fixtures are not benchmarks; and
no performance is currently known.
