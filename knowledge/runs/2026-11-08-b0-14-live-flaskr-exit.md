---
type: run
title: "B0 run 14: live /hunt --target on flask's tutorial app (exit run b)"
description: Live run; the offline-only ordering bug was dropped by the live check again; 0 requests; clean by ruling 2.
---

# B0 run 14: `/hunt examples/tutorial --target http://localhost:5050 --max 1` (exit run b)

- **Target:** as in [run 4](2026-11-08-b0-4-live-flaskr.md); server started for the run and stopped after it.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `069e714`, headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.05 | 6 | 978 | 132,273 | 1,004 |
| Hunt + report | 0.45 | 34 | 10,005 | 513,246 | 26,376 |
| **Total** | **0.50** | | | | |

Agent: 1 hunter (5.3k output, 06:35:45–06:37:26); no verifiers. Requests through the proxy: 0 of 1,200; no writes.

## Result

No drafts. As in [run 12](2026-11-08-b0-12-live-flaskr-rerun.md), the hunter showed the same-second ordering bug in `blog.py` `index` only with Flask's test client in a local copy; its draft had no `Set before running:` line and failed the live check. Hunter drops: the 2^63 id (known, draft 01), empty update form (no bug), deleted user's session (handled), missing field 400 (intended), case-only username differences (design).

## bug-hunter defects found

None. The offline-only drop is an observation, not a defect, by the user's ruling 2 (2026-11-08). Run verdict: **clean**.
