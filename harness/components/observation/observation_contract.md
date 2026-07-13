# Observation contract (seed, structured lane)

- Distilled accessibility tree, flat, with stable element references.
- Every reference is scoped to a `browser_state_epoch`; references from an
  earlier epoch are stale and must fail explicitly, never re-resolve.
- Executor-visible content is tagged `executor`; diagnostic captures are
  judge/orchestrator-only (schemas/trace-event.schema.json).

Implementation arrives with the ADR-0003 baseline decision. This contract
constrains it.
