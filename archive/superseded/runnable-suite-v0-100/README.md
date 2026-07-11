# Superseded incomplete 100-task runnable-suite draft

This directory preserves the exact later partial folder that existed before the repository reconstruction.

It is retained for audit because it introduced ADR-0012, ADR-0013, a 100-task catalog, and 20-task smoke/regression manifests. It is **not active** for three reasons:

1. the project owner subsequently directed that all 140 candidates be runnable before filtering;
2. the folder had lost the rest of the repository and the Git history; and
3. the claimed evaluation package contained only `eval_harness/README.md`, not executable runner source code.

The superseded normalized catalog also contained data defects: many goals were placeholders even though the raw candidate record contained the task intent, and `state_change_expected` was false for state-changing tasks. The active 140-task catalog corrects both while preserving every raw candidate record.
