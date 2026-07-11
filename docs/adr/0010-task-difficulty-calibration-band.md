# ADR-0010: Task difficulty calibration band

- Status: Superseded by ADR-0011 at the time; substance later accepted by ADR-0012
- Date opened: 2026-07-11
- Decision owner: project owner
- Superseded by: [ADR-0011](0011-minimum-success-floor-for-task-candidates.md)
- Later correction: [ADR-0012](0012-reference-success-band-35-to-70.md)

## Historical sequence

This ADR originally proposed a **35–70% inclusive** calibration band. It was not yet accepted when ADR-0011 recorded a 40% minimum. The project owner later clarified that the intended range had always been 35–70%, and ADR-0012 accepted that correction.

The record is retained so a review agent can reconstruct the sequence rather than seeing the earlier 40% mistake silently erased.

## Original rationale

The suite needs enough failures to leave improvement headroom and enough successes to compare winning and failing traces. Tasks near zero success give poor experimental resolution; tasks near saturation leave little room for improvement.

Benchmark-level aggregates may screen source families, but final admission requires repeated task-level results from a pinned strong reference protocol. A benchmark aggregate must never be copied onto every task as though it were a per-task score.

## Still open

ADR-0012 does not decide the reference harness, number of repetitions, confidence-interval rule at the boundaries, or whether visual and structured lanes need separate calibration references.
