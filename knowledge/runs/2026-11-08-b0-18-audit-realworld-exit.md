---
type: run
title: "B0 run 18: /audit src --max 1 on node-express-realworld-example-app (final exit run c)"
description: 1 new low finding with every citation checked against the code; no defect; third clean run in a row, B0's exit.
---

# B0 run 18: `/audit src --max 1` on node-express-realworld-example-app (final exit run c)

- **Target:** as in [run 5](2026-11-08-b0-5-audit-realworld.md). Part kept: `src/app/routes/auth` (5 files); findings 01–30 on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `e5c7cdb` (+ a test comment), headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.08 | — | — | — | — |
| Audit + verify + report | 1.06 | 29,079 | 21,377 | 920,644 | 55,229 |
| **Total** | **1.14** | | | | |

1 auditor, 1 finding-verifier. Preview: 100k + up to 240k; 1 finding verified.

## Result

1 new finding (31), low, confirmed. Every citation in it was checked by hand against the code (each cited line holds the code the finding describes) and `findings.py check --repo` passes. Secrets scan: nothing; npm audit: 14 advisories, all already reported; no suspect dropped. The finding texts stay in the owner's private audit folder (constitution II). The scratch folder and fingerprints were removed; `git status` in the target repo is clean.

## bug-hunter defects found

None. Run verdict: **clean**. With [run 16](2026-11-08-b0-16-json-server-adapters-exit.md) and [run 17](2026-11-08-b0-17-live-flaskr-exit.md), this is the third consecutive run with no bug-hunter defect: B0's exit.
