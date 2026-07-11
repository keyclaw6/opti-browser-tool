# Decision Process

## Purpose

This repository is the durable record of project alignment. A conversational suggestion is not a project decision until its status is changed to `Accepted`.

## Statuses

- `Proposed`: ready for discussion, not binding.
- `Accepted`: binding for implementation and evaluation.
- `Rejected`: considered and intentionally not adopted.
- `Superseded`: replaced by a later ADR.
- `Deprecated`: still present for history but no longer recommended.

## Acceptance protocol

A decision is accepted only after the project owner explicitly approves the ADR number or unmistakably approves its complete substance. The approval date and any amendments are written into the ADR and the decision register.

Suggested conversational forms are:

- `Accept ADR-0002 as written.`
- `Accept ADR-0003 with this amendment: ...`
- `Reject ADR-0004 because ...`
- `Keep ADR-0005 proposed; investigate option B.`

Ambiguous agreement does not change status.

## ADR contents

Every material decision records context, decision, alternatives, consequences, validation plan, status, and date. Decisions that affect experiments also state what evidence would justify revisiting them.

## Implementation linkage

Pull requests and experiment manifests reference relevant ADRs. A change that contradicts an accepted ADR must first propose a superseding ADR.

## Research findings are not automatically architecture decisions

An experiment can establish a result without immediately changing project policy. The result is recorded first; a separate ADR decides whether and where it becomes a default.
