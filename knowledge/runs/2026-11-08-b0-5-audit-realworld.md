---
type: run
title: "B0 run 5: /audit src --max 2 on node-express-realworld-example-app"
description: First live /audit; 22 findings, two bug-hunter defects (absolute-path duplicate, line past end of file).
---

# B0 run 5: `/audit src --max 2` on node-express-realworld-example-app

- **Target:** https://github.com/gothinkster/node-express-realworld-example-app @ `30b68e1e881462b2f4164ea09ab4c4f5699c7b0b`. Parts kept: `src/app/routes/article` (5 files), `src/app/routes/auth` (5 files). Dependency audit: `npm audit --omit=dev --json` in a throwaway copy. No `policy.md`.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `a9b15a9` (before the `author` fix in `efd4511`, so the article part ranked as identity because of `author.mapper.ts`), headless child from the target root.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.28 | 6 | 1,133 | 107,886 | 29,608 |
| Audit + verify + report | 3.68 | 31,651 | 74,192 | 2,674,516 | 249,714 |
| **Total** | **3.96** | | | | |

Agents: 2 auditors in parallel (9.0k and 7.9k output, 84k and 127k cache read, 04:42:53–04:45:01), 10 finding-verifiers in parallel (1.3k–2.7k output each, 04:47:57–04:48:34). Preview estimate: 200k + up to 480k for verification; 10 code findings were verified (≈ 300k at the preview's 30k each).

## Result

22 findings (2 critical, 8 high, 7 medium, 5 low): 12 dependency advisories from `npm audit`, 10 code findings, all confirmed by their verifiers; the finding texts stay in the owner's private audit folder (constitution II).

## bug-hunter defects found

- **Defect 5 (absolute paths):** the article auditor cited absolute paths throughout (`<workspace>/…/<file>:<line>`), so `findings.py dedupe` didn't merge 05 into 04, which has the same root cause cited relatively.
- **Defect 5 (wrong line):** finding 18 cites its sink as `src/main.ts:85`; the file has 57 lines (the code is at 43–44, as 19 cites). Its verifier saw the mismatch and still confirmed it, so 18 and 19 weren't merged either.
- Fixed in `f770d1b`: `findings.py check --repo` drops a finding whose Where cites a missing file, a path outside the repo or a line past the end; absolute paths inside the repo are accepted (rejecting them would have dropped 03), and `dedupe --repo` keys on the relative path. Replayed on this run's files: 05 is merged into 04, and 18 fails the check (`src/main.ts:85: past the end of the file (57 lines)`).
- Found in the preview, before the run: Defect 1 (ranking, fixed in `a9b15a9`) and Defect 3 (`author` read as `auth`, fixed in `efd4511`).

Run verdict: **not clean**.
