---
type: run
title: "B0 run 8: /hunt on json-server's service.ts part"
description: Node/TS hunt of the second src part; 2 drafts kept, but the hunter left the target's server running (defect 7).
---

# B0 run 8: `/hunt src/service.ts src/random-id.ts src/where-operators.ts --max 1` on json-server

- **Target:** as in [run 3](2026-11-08-b0-3-json-server.md), the part run 3's `--max 1` left out (`random-id.ts`, `service.ts`, `where-operators.ts`). Install: `pnpm install --frozen-lockfile --ignore-scripts` in throwaway copies. Run 3's drafts 01–04 were on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `2ef6a7f`, headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.31 | 4 | 712 | 62,966 | 35,446 |
| Hunt + verify + drafts | 1.20 | 76 | 20,709 | 1,096,393 | 84,230 |
| **Total** | **1.51** | | | | |

Agents: 1 hunter (8.5k output, 327k cache read, 05:18:06–05:20:30), 2 verifiers in parallel (1.8k–1.9k output each, 05:21:00–05:21:40).

## Result

Kept (both `VERDICT: REPRODUCES`): 05 `_embed` of an object (singular) resource crashes with 500 (`service.ts` `embed`); 06 `DELETE …?_dependent=` also deletes unrelated records whose foreign key was already `null` (`destroyById` / `deleteDependents`).

Dropped by the hunter: `null` or plain values in a collection (same cause as #1709); singular `_embed` with numeric foreign keys (same family as draft 02); nothing wrong in `random-id.ts` and `where-operators.ts` beyond draft 01; `constructor`/`toString` resource names (#1780).

## bug-hunter defects found

- **Defect 7:** the hunter started `node … src/bin.ts` in its copy and never stopped it. The command's cleanup failed (`rm: cannot remove '/tmp/tmp.…/hunter-1/copy': Device or resource busy`), and the session had to find the process with `Get-CimInstance` and stop it by hand. The prompts only covered the stub server. Fixed in `e203dbf`: agents list every background PID in `<SCRATCH>/bg.pids` and stop it; `scripts/reap.py` stops whatever is still listed before `/hunt` and `/audit` delete the scratch folder, and a folder that can't be removed is reported.

Run verdict: **not clean**.
