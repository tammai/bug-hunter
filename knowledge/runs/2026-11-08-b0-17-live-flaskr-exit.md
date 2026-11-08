---
type: run
title: "B0 run 17: live /hunt --target on flask's tutorial app (final exit run b)"
description: Live run through the proxy, 24 of 1,200 requests, writes listed; offline-only bug dropped per ruling 2; clean.
---

# B0 run 17: `/hunt examples/tutorial --target http://localhost:5050 --max 1` (final exit run b)

- **Target:** as in [run 4](2026-11-08-b0-4-live-flaskr.md); server started for the run and stopped after it.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `e5c7cdb` (+ a test comment), headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.05 | 6 | 980 | 132,279 | 1,081 |
| Hunt + report | 0.58 | 48 | 12,652 | 708,032 | 33,735 |
| **Total** | **0.63** | | | | |

Agent: 1 hunter (7.9k output, 07:03:05–07:06:32); no verifiers. Requests: 24 of 1,200 through the proxy; writes listed for clean-up (6 registrations, 8 logins, 8 posts created).

## Result

No drafts. The same-second ordering bug in `blog.py` `index` was again shown only with a local copy (each proxied request took about 2 s, so no two live posts shared a second); its draft had no `Set before running:` line and failed the live check, and the report named it and the offline rerun that would verify it. Other hunter notes: NUL/invalid UTF-8 in register and login handled; empty-title update form (design); forged session `user_id` 500 (needs the secret key, below the bar); 2^63 id (known, draft 01). The proxy was stopped, temp folders removed; `git status` in the target repo is clean.

## bug-hunter defects found

None. The offline-only drop is an observation by the user's ruling 2. Run verdict: **clean**.
