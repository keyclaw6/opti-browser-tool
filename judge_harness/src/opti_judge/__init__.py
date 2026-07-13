"""opti-judge: evaluation-plane judge instrumentation (T0 admission, T1
deterministic cross-checks, T2 panel scaffolding, T3 quarantine).

Provisional infrastructure implementing the layering proposed in ADR-0016.
That ADR is Proposed, not Accepted; this package's existence does not change
its status (docs/DECISION_PROCESS.md).

Structural guarantees carried by this code:

- **Verifiers are the only scorers.** Nothing in this package writes or
  mutates a score. Judges emit *flags*; unresolved disagreement is
  quarantined for the project owner, never averaged into a result.
- **Trust is earned, not assumed.** A T2 judge's flags carry
  ``trusted: false`` until the judge has measured precision/recall on the
  calibration corpus at or above its per-role operating point.
- **Evidence contracts are enforced.** Each role sees only the trace
  visibility classes its contract allows; ``restricted`` material is never
  loadable through this package's evidence API.
- **No LLM in gate decisions.** T2 output feeds diagnostics and the
  quarantine queue; the loop's accept/reject stays deterministic
  (ADR-0015 §5.3).
"""

__version__ = "0.1.0"
