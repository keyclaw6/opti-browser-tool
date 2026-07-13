# Infrastructure mounts (optimizer read-only)

Session interface + backend adapters, executor model configuration, tracer,
and budgets live here once ADR-0003/0004 are decided. The optimizer never
edits this tree; the file guard enforces it (only harness/components/ is
writable). Verifiers, bridges, and suites live outside harness/ entirely.
