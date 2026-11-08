---
type: run
title: "B0 run 9: /hunt cmd --max 1 on godotenv"
description: Go CLI hunt of cmd/godotenv; 1 draft kept and verified, no bug-hunter defect.
---

# B0 run 9: `/hunt cmd --max 1` on godotenv

- **Target:** as in [run 2](2026-11-08-b0-2-godotenv.md), part `cmd/godotenv` (`cmd.go`). No installs. Run 2's drafts 01–03 were on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `2ef6a7f`, headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.24 | 4 | 620 | 62,934 | 26,538 |
| Hunt + verify + drafts | 0.71 | 44 | 10,579 | 502,559 | 58,267 |
| **Total** | **0.95** | | | | |

Agents: 1 hunter (4.0k output, 123k cache read, 05:18:03–05:19:01), 1 verifier (1.4k output, 05:19:19–05:19:46).

## Result

Kept (`VERDICT: REPRODUCES`): 04 the `godotenv` command exits 1 and logs `exit status N` when the wrapped command fails, instead of passing on its exit code (`cmd.go` `main`, 51–54).

Dropped by the hunter: spaces and a trailing comma in `-f` lists (malformed input, clear error); signals not forwarded (#21); partial load when files are missing (#175).

## bug-hunter defects found

None. Run verdict: **clean**. It completed before defect 7 was fixed and ran on `2ef6a7f`; it started no background process.
