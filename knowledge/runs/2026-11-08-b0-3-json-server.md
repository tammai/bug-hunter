---
type: run
title: "B0 run 3: /hunt --max 1 on json-server"
description: Node/TS service hunt with a locked pnpm install; 4 drafts kept and verified, no bug-hunter defect.
---

# B0 run 3: `/hunt --max 1` on json-server

- **Target:** https://github.com/typicode/json-server @ `89a34a44b7a6a5311dc84f3b8a1b8b45c0905aea`, part `src` (`app.ts`, `bin.ts`, `matches-where.ts`, `paginate.ts`, `parse-where.ts`), edge inputs `generic`, `node`. Install: `pnpm install --frozen-lockfile --ignore-scripts` (in throwaway copies only). Left out by `--max 1`: `random-id.ts`, `service.ts`, `where-operators.ts`, `src/adapters/`.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `a9b15a9`, headless child from the target root, as in [run 1](2026-11-08-b0-1-python-markdown2.md).
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.32 | 4 | 767 | 61,268 | 37,090 |
| Hunt + verify + drafts | 2.11 | 35,408 | 42,811 | 1,583,266 | 121,355 |
| **Total** | **2.44** | | | | |

Agents: 1 hunter (14.2k output, 575k cache read, 04:41:15–04:46:12), 4 verifiers in parallel (1.3k–2.4k output each, 04:47:24–04:48:08). The open-issues list was cut at 500, so the preview said duplicates of older issues can't be ruled out.

## Result

Kept (all `VERDICT: REPRODUCES`), in `~/.bug-hunter/github.com/typicode/json-server/drafts/`:

1. A field name ending in an operator suffix (`?opt_in=true`) is read as an operator on a shorter field, so the query returns `[]` (`parse-where.ts` `splitKey`).
2. Numeric query values never match ids stored as text (`parse-where.ts` `coerceValue`, `matches-where.ts`). The session flagged a possible duplicate of the vaguely titled #1609.
3. A second `?` in the query string cuts the query short (`app.ts` `parseListParams`).
4. `--host` is ignored, so the server listens on every interface (`bin.ts`). The session noted that one side claim in this draft (`[::1]` answering under `--host 127.0.0.1`) was seen by the hunter only; the main repro was re-run.

Dropped by the hunter: known open issues (#1731, #1757, #1549, #1721, #909); low-impact cases (legacy `_startsWith`/`_endsWith`, a trailing bare colon, a non-numeric `--port`).

## bug-hunter defects found

- **Defect 8** (ruled a defect by the user on 2026-11-08, after this record was first written as an observation): draft 04 carried a side claim (`[::1]` answering under `--host 127.0.0.1`) that only the hunter saw; its verifier re-ran the steps and passed it. Fixed after `2e2f627`: a draft may claim only what its steps' output shows, and the verifier fails an unshown claim (AC-015, checked by eval).

Run verdict: **not clean** (by the later ruling).
