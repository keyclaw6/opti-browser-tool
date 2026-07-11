# ADR-0003: Initial browser backend and action mechanisms

- Status: Proposed
- Date proposed: 2026-07-11

## Context

The first backend must support difficult interfaces, detailed instrumentation, reproducible sessions, and later cross-browser comparison. Native pointer and keyboard events may behave differently from DOM-triggered actions.

## Decision

Start research execution on Chromium through Playwright, with Chrome DevTools Protocol instrumentation where Playwright does not expose sufficient observability. Put both behind a browser-neutral session interface.

Treat `native`, `playwright`, and `dom` as explicit action mechanisms recorded in every action event. Do not silently convert one mechanism into another. A policy may request a fallback, but the trace must preserve the attempted mechanism, failure, fallback decision, and final mechanism.

Provide a backend capability manifest so tests can declare requirements without assuming Chromium. Add Firefox and WebKit adapters only after the vertical slice is stable.

## Alternatives considered

- Selenium first: broad ecosystem, weaker integrated tracing for this research use.
- Raw CDP first: maximal control, excessive early implementation surface and Chromium lock-in.
- OS-level automation only: human-like input, but poor deterministic state management and slower debugging.

## Consequences

Chromium is a research baseline, not a declared final production browser. Cross-browser compatibility remains an explicit later test. The action mechanism becomes an experimental variable rather than an implementation detail.

## Validation and revisit trigger

Validate on tasks involving popups, scrolling, dynamic updates, tabs, forms, content-editable fields, failed clicks, and session state. Revisit if Playwright materially interferes with native behavior or cannot capture required evidence.
