---
type: run
title: "B0 run 12: live /hunt --target rerun on flask's tutorial app"
description: Live rerun; a bug provable only with the local test client was dropped by the live draft check (observation, not counted as a defect).
---

# B0 run 12: `/hunt examples/tutorial --target http://localhost:5050 --max 1` (rerun)

- **Target:** as in [run 4](2026-11-08-b0-4-live-flaskr.md); the same server and database (run 4's users still in it). Draft 01 was on the known list. Server stopped after the run.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `e203dbf`, headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.25 | 6 | 1,081 | 107,412 | 25,892 |
| Hunt + report | 0.96 | 26,439 | 17,721 | 679,374 | 52,891 |
| **Total** | **1.21** | | | | |

Agents: 1 hunter (9.3k output, 05:32:12–05:36:22); no verifiers. Requests: 20 of 1,200; 16 writes (3 registrations, 3 logins, 9 posts created, 1 rejected create), all listed for clean-up.

## Result

No drafts. The hunter proved one bug only with Flask's test client: posts created in the same second list oldest-first (`blog.py` `index` sorts by `created`, stored to the second, with no `id` tiebreak). Through the live server its posts landed in different seconds, so it couldn't show it there. Its draft had no `Set before running:` line, failed the live `drafts.py check`, and was dropped before verification; the session suggested an offline `/hunt examples/tutorial --max 1` to have it verified. Other hunter notes (unverified): missing field → 400 (normal); whitespace-only titles accepted (below the bar); odd bytes stored; form refill after a failed update; default `SECRET_KEY` and GET logout (configuration).

## bug-hunter defects found

None counted. **Observation for later (not fixed in B0):** a live hunt has no route for a bug the hunter can prove only offline; the live draft check drops it. That follows the live rules as written (a live draft's steps run against `$BASE`), and the report names the bug and the offline rerun that would verify it, so nothing is lost silently.

Run verdict: **clean**.
