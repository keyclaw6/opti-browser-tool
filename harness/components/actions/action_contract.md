# Action contract (seed, structured lane)

Primitives only at seed: click, type, select, scroll, navigate, tab ops.

Every action declares:
- pre-execution validation (target exists in current epoch, is interactable);
- postconditions the runtime verifies after dispatch;
- an explicit `action_result` trace event carrying mechanism, target
  reference + epoch, and the verification outcome.

Silent failure is a defect of this component.
