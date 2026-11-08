---
type: run
title: "B0 run 4: live /hunt --target on flask's tutorial app"
description: First live-target hunt through live_proxy.py; 1 draft kept and verified, 17 of 1,200 requests, no bug-hunter defect.
---

# B0 run 4: `/hunt examples/tutorial --target http://localhost:5050 --max 1`

- **Target:** https://github.com/pallets/flask @ `49943b5a94413a530761350f04e896f76e8d620e`, `examples/tutorial/flaskr` (`__init__.py`, `auth.py`, `blog.py`, `db.py`), edge inputs `generic`, `python-cli`, `live-http`. Server: `uv sync --frozen` in the clone, `flask --app flaskr init-db`, `flask --app flaskr run --port 5050` (localhost, so writes allowed, no accounts). Stopped after the run.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `f770d1b`, headless child from the clone's root with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview (incl. `live_proxy.py --check`) | 0.26 | 6 | 979 | 105,651 | 27,481 |
| Hunt + verify + drafts | 0.85 | 46 | 15,335 | 608,919 | 60,722 |
| **Total** | **1.11** | | | | |

Agents: 1 hunter (5.4k output, 121k cache read, 05:10:18–05:12:14), 1 verifier (2.5k output, 05:12:44–05:13:51). Request budget 1,200 (200 × (1 + 5)); 17 used, 10 of them writes: 3 registrations (users named `bh…`), 3 logins, 3 failed deletes (500), 1 rejected create (400). The report listed them for clean-up.

## Result

Kept (`VERDICT: REPRODUCES`, re-run against the server from the draft alone), `~/.bug-hunter/github.com/pallets/flask/drafts/01.md`: an update or delete URL with a post id above 2^63−1 gives a 500 instead of a 404 (`blog.py` `get_post`; SQLite `OverflowError`). The draft uses `$BASE`, names no host or token and passes `drafts.py check --target`.

Dropped by the hunter: missing `body` → 400 (Werkzeug's intended behaviour); session for a deleted user → logged out (no crash); `SECRET_KEY="dev"` (documented tutorial default); case-sensitive usernames (design).

## bug-hunter defects found

None. Run verdict: **clean**.
