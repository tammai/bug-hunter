---
type: run
title: "B0 run 13: /hunt src/adapters --max 1 on json-server (exit run a)"
description: 1 draft kept and verified; the verifier wrote srv.pid into the target repo (defect 9).
---

# B0 run 13: `/hunt src/adapters --max 1` on json-server (exit run a)

- **Target:** as in [run 10](2026-11-08-b0-10-json-server-adapters.md); drafts 01–08 on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `069e714` (tree reaping, recorded job trees, safe tool lookup, unshown-claim rule), headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.13 | 6 | 692 | 132,262 | 10,884 |
| Hunt + verify + drafts | 0.87 | 66 | 18,162 | 868,274 | 53,046 |
| **Total** | **1.00** | | | | |

Agents: 1 hunter (6.8k output, 06:35:54–06:38:04), 1 verifier (3.6k output, 06:38:26–06:39:38).

## Result

Kept (`VERDICT: REPRODUCES`): 09 ids generated for records without an `id` aren't saved, so each reload of `db.json` gives the record a new id and the old one 404s (`normalized-adapter.ts` `NormalizedAdapter.read`). Dropped by the hunter: `null` items (#1709), boolean/object ids (same cause as 08), `$schema` overwrite (intended, tested), failed write skips its handler (07), self-reload after writes (#1288), `1e21` ids (`JSON.parse`, below the bar). No process was left running; the scratch folder was removed.

## bug-hunter defects found

- **Defect 9:** the verifier ran `cd <copy> && printf … && exec node … > srv.out 2>&1 & echo $! > srv.pid`. The `&` backgrounds the whole `&&` list, `cd` included, so `echo $! > srv.pid` ran in the agent's starting folder, the target repo, and wrote `srv.pid` there (constitution III). The verifier noticed and moved it out, so the repo ended clean. Fixed in `5685cae`: the isolation prefix now `cd`s into the agent's copy (or its scratch folder before a copy exists), so a relative write never lands in the repo whatever the command's shape.

Run verdict: **not clean**.
