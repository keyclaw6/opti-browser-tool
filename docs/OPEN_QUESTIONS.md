# Open Questions

These are intentionally unresolved. They should be answered through the workstreams and explicit decisions rather than incidental implementation choices.

1. Which saved and external browser-agent repositories belong in the first harness survey?
2. Which existing harness or combination of components should be the first experimental baseline?
3. Which browser engine, control layer, and action mechanisms should that baseline use?
4. How should visual-first, terminal/CLI, and later hybrid research be isolated?
5. Which benchmark environments and individual tasks are relevant, runnable, redistributable, and legally modifiable?
6. Which tasks should make up the provisional 20-task bring-up set, the stable 10–20-task smoke suite, and the approximately 100-task primary suite?
7. How should unstable tasks, repeated trials, regression promotion, and the hidden holdout be managed?
8. Which completion verifiers and LLM judges are needed, what evidence may each see, and how will false-positive and false-negative rates be calibrated?
9. What trace and artifact representation best supports replay, diagnosis, redaction, and cross-harness comparison?
10. How should the two reference auto-research frameworks be adapted rather than copied blindly?
11. Which executor and judge models are approved, with which exact API identifiers, snapshots, settings, and data policies?
12. Which infrastructure will host browser workers, artifacts, model endpoints, and hidden evaluation?
13. What detailed policy is required before permitted live-site testing?
14. Should the repository remain public, and which license should it use?
15. Which implementation language, runtime, package manager, and CI structure should be adopted after the first baseline is selected?
