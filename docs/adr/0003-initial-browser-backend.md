# ADR-0003: Initial browser backend and action mechanisms

- Status: Open
- Date opened: 2026-07-11
- Approval state: Not accepted

## Question

Which existing browser, automation substrate, or browser-agent harness should form the first runnable baseline, and which action mechanisms should it expose?

## Current position

No browser backend or control library is preferred. In particular, Playwright is not selected as the default starting point merely because it is familiar or well instrumented.

The first choice must follow a structured review of current browser-agent harnesses and the repositories collected for this project. The project may adopt an existing harness, reuse selected components, or build a thin experimental layer over a lower-level browser interface. That outcome remains open.

## Research required

For each serious candidate, record and compare:

- browser engine and control layer;
- structured, accessibility, screenshot, and multimodal observations;
- DOM-triggered, protocol-level, and native pointer/keyboard actions;
- tabs, frames, downloads, dialogs, login, and persistent sessions;
- dynamic-page and stale-reference handling;
- recovery behavior and action verification;
- tracing, network, console, and browser-state observability;
- cross-browser support and transfer;
- benchmark integration and reproducibility;
- implementation maturity, maintenance, extensibility, and license; and
- known failure modes or evidence from published evaluations.

The review should produce falsifiable hypotheses, not only a feature checklist. Small comparison tests should then target the differences predicted to matter.

## Decision gate

A first-baseline decision memo must name the evidence, alternatives, hypotheses, expected advantages, likely regressions, and the minimum test needed to reconsider the choice. Explicit project approval is required before implementation treats any backend as the baseline.
