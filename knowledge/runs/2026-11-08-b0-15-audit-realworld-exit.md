---
type: run
title: "B0 run 15: /audit src --max 1 on node-express-realworld-example-app (exit run c)"
description: First audit with check --repo, reap and the new auditor prompt; 2 new low findings; one cites a line off by one, which its verifier noticed and confirmed anyway.
---

# B0 run 15: `/audit src --max 1` on node-express-realworld-example-app (exit run c)

- **Target:** as in [run 5](2026-11-08-b0-5-audit-realworld.md). Part kept: `src/app/routes/auth` (`auth.controller.ts`, `auth.service.ts`, `auth.ts`, `register-input.model.ts`, `registered-user.model.ts`); findings 01–28 on the known list.
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

2 new findings, both low, both traced and confirmed: 29 emails compared case-sensitively and unvalidated at signup and login (`auth.service.ts:39`); 30 passwords past 72 bytes silently truncated by bcrypt (`auth.service.ts:41`). The 14 npm advisories were all already reported; the secrets scan added nothing; no suspect failed `check --repo` or was dropped. A verifier also noted a functional (not security) bug outside the report: password update keeps surrounding spaces that login trims.

## bug-hunter defects found

- **Open, awaiting a ruling:** finding 29 cites `src/prisma/schema.prisma:44` for `email @unique`, which is on line 45. Its verifier noticed and confirmed the finding anyway. `check --repo` passes it because line 44 exists; only a line past the end is caught mechanically. Like run 5's finding 18 (whose cited line didn't exist), the verifier accepted a citation that doesn't hold the quoted code, which its prompt asks it to check.

Run verdict: **pending the ruling** (clean if an off-by-one citation in a non-root hop is not a defect).
