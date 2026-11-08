---
type: run
title: "B0 run 11: /hunt autoload --max 1 on godotenv"
description: One-file Go part; no bugs, everything dropped with reasons, no bug-hunter defect.
---

# B0 run 11: `/hunt autoload --max 1` on godotenv

- **Target:** as in [run 2](2026-11-08-b0-2-godotenv.md), part `autoload` (`autoload.go`, one `init()` calling `godotenv.Load()`). Drafts 01–04 were on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `e203dbf`, headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.24 | 4 | 622 | 63,001 | 26,632 |
| Hunt + report | 0.66 | 17,378 | 8,913 | 364,284 | 49,527 |
| **Total** | **0.90** | | | | |

Agents: 1 hunter (3.1k output, 05:32:10–05:33:23); no verifiers (no findings).

## Result

No drafts. Dropped by the hunter: `${VAR}` expansion prefers the file over the environment (cause in `parser.go`, outside the part; close to #241, #155, #189); one bad line loads nothing (autoload discards the error by design); missing `.env` ignored (#192, #213, #236); empty existing variable kept (documented); Windows key casing (#295, #222); `=C:` entries (same cause as draft 02); `Load()` reads only the current folder (#76, #126, #165, #43).

## bug-hunter defects found

None. Run verdict: **clean**.
