# Upstream task-metadata notices — Batch 1

This file records the license evidence checked while constructing Batch 1. It is an engineering record, not legal advice. The project stores selected task identifiers and task metadata for research planning; it does not vendor benchmark environments, archived webpages, website assets, or model trajectories.

| Source | Pinned source | License evidence checked | Notes |
|---|---|---|---|
| REAL / AGI SDK | `agisdk 0.3.5`, REAL v1 task manifests | Bundled `LICENSE` file states Apache License 2.0 | Package metadata contains an MIT classifier while the bundled license text is Apache-2.0. The bundled license text is treated as controlling evidence for this inventory; this mismatch should be rechecked before redistribution beyond task-review metadata. |
| WorkArena++ | `browsergym-workarena 0.5.3` | Package metadata and bundled `LICENSE` state Apache-2.0 | ServiceNow instance access and dataset terms remain separate operational requirements. |
| WebArena-Verified | `webarena-verified 1.2.3` | Repository and bundled `LICENSE` state Apache-2.0 | The inventory includes task IDs and prompts, not environment images or network traces. |
| VisualWebArena | `libvisualwebarena 0.0.15` | Bundled `LICENSE` is MIT | Referenced task images and environment assets are not copied into this repository. |
| WARC-Bench | Git commit `98d213ccd2b4380761738e1d144467a8695e37c5` | Upstream README states MIT | Archived real-web content may carry rights distinct from benchmark code. This repository stores only selected task metadata and does not redistribute WARC/WACZ archives. |

## Review requirement

Before the final suite is published or redistributed, recheck the exact upstream revision, task-data terms, environment-image terms, and any archived-content restrictions. Record any attribution or non-commercial conditions in the final task manifest.
