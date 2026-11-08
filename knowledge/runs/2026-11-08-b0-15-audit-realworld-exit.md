---
type: run
title: "B0 run 15: /audit src --max 1 on node-express-realworld-example-app (exit run c)"
description: First audit with check --repo, reap and the new auditor prompt; 2 new low findings; one cites a line off by one, which its verifier noticed and confirmed anyway.
---

# B0 run 15: `/audit src --max 1` on node-express-realworld-example-app (exit run c)

- **Target:** as in [run 5](2026-11-08-b0-5-audit-realworld.md). Part kept: `src/app/routes/auth` (5 files); findings 01–28 on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `069e714`, headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.29 | 6 | 1,176 | 108,062 | 30,725 |
| Audit + verify + report | 1.17 | 58 | 20,139 | 852,645 | 89,350 |
| **Total** | **1.46** | | | | |

Agents: 1 auditor (5.7k output, 06:35:56–06:36:59), 2 finding-verifiers in parallel (1.8k and 2.2k output, 06:37:33–06:37:58). Preview: 100k + up to 240k; 2 findings verified (≈ 60k).

## Result

2 new findings (29, 30), both low, both traced and confirmed. The 14 npm advisories were all already reported; the secrets scan added nothing; no suspect failed `check --repo` or was dropped. The finding texts stay in the owner's private audit folder (constitution II).

## bug-hunter defects found

- **Defect 10** (ruled a defect by the user, 2026-11-08): finding 29 cites a line in `src/prisma/schema.prisma` one above the code it quotes. Its verifier noticed and confirmed the finding anyway. `check --repo` passes it because the cited line exists; only a line past the end is caught mechanically. Like run 5's finding 18 (whose cited line didn't exist), the verifier accepted a citation that doesn't hold the quoted code, which its prompt asks it to check.

Fixed test-first: the finding-verifier now opens each file at exactly the cited line and returns `NOT CONFIRMED — wrong citation: …` when that line holds other code. Checked by eval on finding 29 itself: `CONFIRMED` before the fix, `NOT CONFIRMED — wrong citation: …` naming the right line after, and `CONFIRMED` with the line corrected (AC-018).

Run verdict: **not clean**.
