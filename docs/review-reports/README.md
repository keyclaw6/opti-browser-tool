# Review Reports

Independent audit agents commit their completed reports here. Each audit runs
from the reviewed `main` SHA on its own branch and changes only its report file.

Expected reports:

| Part | Repository path | Finding prefix |
|---|---|---|
| Foundations and bring-up | `docs/review-reports/opti-audit-part-1-foundations.md` | `FOUND-` |
| Research loop and convergence | `docs/review-reports/opti-audit-part-2-convergence.md` | `CONV-` |
| Security and operations | `docs/review-reports/opti-audit-part-3-operations.md` | `OPS-` |

## Delivery contract

Each reviewer:

1. clones the latest `main`;
2. records the reviewed base SHA;
3. creates a unique `codex/audit-*` branch;
4. performs the audit without changing product code or project documentation;
5. writes exactly one report at the assigned path;
6. stages and commits only that report;
7. pushes the branch to `origin`; and
8. returns only the reviewed SHA, report path, branch, report commit SHA, and
   push status.

Reports must not contain credentials, private keys, unredacted benchmark
secrets, or hidden-holdout contents. The committed reports are the durable
source material for later synthesis; they should not be rewritten while
findings are being merged.
