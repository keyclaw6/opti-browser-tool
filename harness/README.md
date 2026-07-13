# harness/ — the harness-under-test (provisional scaffold)

**Status:** scaffold implementing `docs/architecture/COMPONENT_TREE.md`
in support of ADR-0015 (Accepted 2026-07-13). It contains **no browser code** and selects
**no backend** — ADR-0003 remains open; accepting ADR-0015 did not settle it.

- `components/` — the eight optimizer-evolvable components. **The only surface
  the optimizer may write** (enforced by the loop's git file guard).
- `infra/` — optimizer read-only mounts (session, model config, tracer, budgets).
- `lanes/` — pinned observation/action configurations over one component tree.

Each component carries a `component.json` registration; the loop's E1 static
audit checks that changed files are registered and consistent. Seed content is
deliberately minimal to protect attribution (COMPONENT_TREE.md §6).
