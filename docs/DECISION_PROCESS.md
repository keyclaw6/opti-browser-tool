# Decision Process

## Purpose

This repository is the durable record of project alignment. A conversational suggestion, implementation convenience, or research finding is not a project decision until an ADR is explicitly accepted.

## Statuses

- `Open`: the question is recorded, but the project is not ready to choose an option.
- `Proposed`: a concrete option is ready for decision discussion, but is not binding.
- `Accepted`: binding for implementation and evaluation.
- `Rejected`: considered and intentionally not adopted.
- `Superseded`: replaced by a later ADR.
- `Deprecated`: still present for history but no longer recommended.

Open and proposed ADRs may contain candidate directions, but those directions are not defaults and must not be implemented as though they were accepted.

## Acceptance protocol

A decision is accepted only after the project owner explicitly approves the ADR number or unmistakably approves its complete substance. The approval date and any amendments are written into the ADR and the decision register.

Example forms are:

- `Keep ADR-0003 open while we research existing harnesses.`
- `Move ADR-0003 to proposed with option B.`
- `Accept ADR-0002 as written.`
- `Accept ADR-0004 with this amendment: ...`
- `Reject ADR-0005 because ...`

Ambiguous agreement does not change status.

## ADR contents

An open ADR records the question, candidate directions if useful, evidence required, and the decision gate. An accepted ADR additionally records the chosen decision, alternatives, consequences, validation plan, approval date, and revisit triggers.

## Implementation linkage

Pull requests and experiment manifests reference relevant ADRs. A change must not silently settle an open ADR. A change that contradicts an accepted ADR must first propose a superseding ADR.

## Research findings are not automatically architecture decisions

An experiment or source review can establish a result without immediately changing project policy. The evidence is recorded first; a separate decision determines whether and where it becomes a default.
