"""opti-loop: deterministic conductor for the auto-research loop.

Reference implementation of ADR-0015 (loop), ADR-0005 (gate ladder), and
ADR-0016 (evaluation layering), all Accepted 2026-07-13. Loop activation is
separately gated on the pre-activation requirements recorded in those ADRs.

Design provenance:
- loop skeleton, file guard, regression promotion: neosigmaai/auto-harness;
- change manifests, attribution, component-level pivot, analysis-first
  iteration folders: china-qijizhifeng/agentic-harness-engineering;
- fail-closed validity, noise-band comparison instead of a best-score
  ratchet, no LLM in gate decisions, generality lint: this project's ADRs.

No LLM participates in any decision made by this package.
"""

__version__ = "0.1.0"
