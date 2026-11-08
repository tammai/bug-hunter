---
type: run
title: "B0 run 10: /hunt src/adapters --max 1 on json-server"
description: 2 drafts kept, but the hunter again left unlisted servers running and blocked a verifier (defect 7 again).
---

# B0 run 10: `/hunt src/adapters --max 1` on json-server

- **Target:** as in [run 3](2026-11-08-b0-3-json-server.md), part `src/adapters` (`normalized-adapter.ts`, `observer.ts`). Drafts 01–06 were on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `e203dbf` (bg.pids rule and `reap.py`), headless child with every `ORCA_*` variable unset. First exit run after the defect 7 fix.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.31 | 4 | 704 | 62,997 | 35,525 |
| Hunt + verify + drafts | 1.87 | 20,710 | 34,405 | 1,516,170 | 124,014 |
| **Total** | **2.18** | | | | |

Agents: 1 hunter (7.6k output, 05:32:10–05:34:04), 3 verifiers (draft 08: 4.2k output, 05:34:48–05:36:08; draft 07 first try: 6.4k output, 05:34:48–05:39:51, `CANNOT RUN`; draft 07 second try: 2.8k output, 05:40:37–05:41:28).

## Result

Kept (both `VERDICT: REPRODUCES`): 07 after one failed write the server stops reloading `db.json` until restart (`observer.ts` `Observer.write`); 08 records with `"id": null` are listed but every by-id request returns 404 (`normalized-adapter.ts` `NormalizedAdapter.read`).

Dropped by the hunter: `null`/primitive items crash startup (#1709); records without an id get a new id on each reload (by design); a failed write's record stays in memory (outside the part); nothing wrong in `$schema` stripping or singular resources.

## bug-hunter defects found

- **Defect 7 again:** the hunter left two json-server processes (ports 3457, 3458) running and didn't list them in `bg.pids`, so `reap.py` couldn't stop them. The first verifier for 07 couldn't bind 3457 and returned `CANNOT RUN`; the session killed both by PID and re-dispatched. Fixed in `9243852`: the isolation prefix every agent Bash call starts with sets an `EXIT` trap that lists each background job in `<scratch>/bg.pids`, so listing no longer depends on the agent.

Run verdict: **not clean**.
