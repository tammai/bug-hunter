---
type: run
title: "B0 run 16: /hunt src/adapters --max 1 on json-server (final exit run a)"
description: No new bugs; every suspect dropped with a reason; no process left, repo untouched; clean.
---

# B0 run 16: `/hunt src/adapters --max 1` on json-server (final exit run a)

- **Target:** as in [run 10](2026-11-08-b0-10-json-server-adapters.md); drafts 01–09 on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `e5c7cdb` (+ a test comment), headless child with every `ORCA_*` variable unset. First run after the last fix.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.12 | 4 | 692 | 87,858 | 10,779 |
| Hunt + report | 0.47 | 28 | 8,623 | 448,174 | 31,706 |
| **Total** | **0.59** | | | | |

Agent: 1 hunter (4.8k output, 07:03:10–07:04:08); no verifiers.

## Result

No drafts. The hunter dropped every suspect on reading, with a reason: `null`/primitive items (#1709); boolean/object ids (draft 08); `$schema` overwrite (intended, tested); unsaved generated ids and stuck reload (drafts 09, 07); self-reload (#1288); a `$schema` resource (not creatable; related #1780); JSON number forms and >2^53 ids (`JSON.parse`); top-level array db (not a valid db file). No background process was left running, the scratch folder was removed, and `git status` in the target repo is clean.

## bug-hunter defects found

None. Run verdict: **clean**.
