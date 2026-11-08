---
type: run
title: "B0 run 6: /audit src --max 2 rerun on node-express-realworld-example-app"
description: Audit rerun after the ranking and citation fixes; both auth parts audited, 6 new findings, no bug-hunter defect.
---

# B0 run 6: `/audit src --max 2` rerun on node-express-realworld-example-app

- **Target:** as in [run 5](2026-11-08-b0-5-audit-realworld.md). With the ranking fixes (`a9b15a9`, `efd4511`) the kept parts are both `src/app/routes/auth` parts. The earlier 22 findings were the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `f770d1b` (`findings.py check --repo` and `dedupe --repo` in use), headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.27 | 6 | 1,082 | 109,567 | 28,735 |
| Audit + verify + report | 2.87 | 26,347 | 58,000 | 2,246,724 | 183,925 |
| **Total** | **3.14** | | | | |

Agents: 2 auditors in parallel (4.6k and 10.0k output, 05:06:32–05:09:13), 6 finding-verifiers in parallel (1.8k–2.5k output each, 05:11:18–05:11:51). Preview estimate: 200k + up to 480k; 6 findings verified (≈ 180k at 30k each).

## Result

6 new findings (23–28), all confirmed: 3 medium, 3 low; none critical or high. The second auditor found nothing beyond earlier findings. The secrets scan found nothing new; the 14 npm advisories were all already reported and were deduplicated against the earlier run. No suspect failed `check` or was dropped. The finding texts stay in the owner's private audit folder (constitution II).

## bug-hunter defects found

None. Run verdict: **clean**.
