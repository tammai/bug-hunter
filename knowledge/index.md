---
type: index
title: Knowledge map
description: Entry point. Read this, then open only the docs relevant to the task.
---

# Knowledge map

One line per doc: path — what it answers (≤12 words). Keep this file under ~80 lines; split into `<folder>/index.md` files when it grows.

Background: [BRIEF.md](../BRIEF.md) — where the recipe comes from; [PRD](../docs/sdlc/prd.md); [constitution](../docs/sdlc/constitution.md).

## Conventions
-

## Decisions
- [decisions/drafts-location.md](decisions/drafts-location.md) — where drafts and posted.json live, and why that layout

## Gotchas
- [gotchas/copying-a-target-repo.md](gotchas/copying-a-target-repo.md) — why agents copy targets only with throwaway.py
- [gotchas/isolating-agents-without-a-sandbox.md](gotchas/isolating-agents-without-a-sandbox.md) — why isolate.py drops, keeps and refuses what it does
- [gotchas/detecting-secrets-in-free-text.md](gotchas/detecting-secrets-in-free-text.md) — why findings are checked against found secrets, not shapes
- [gotchas/redacting-logged-requests.md](gotchas/redacting-logged-requests.md) — why the stub parses, decodes and withholds before logging
- [gotchas/stopping-agent-processes-on-windows.md](gotchas/stopping-agent-processes-on-windows.md) — why agents' servers are listed by the prefix and stopped with reap.py

## Runbooks
- [runbooks/release.md](runbooks/release.md) — how to cut, smoke-test and roll back a release

## Runs
- [runs/2026-11-08-b0-1-python-markdown2.md](runs/2026-11-08-b0-1-python-markdown2.md) — B0 run 1: Python CLI hunt, fence defect found
- [runs/2026-11-08-b0-2-godotenv.md](runs/2026-11-08-b0-2-godotenv.md) — B0 run 2: Go module hunt, clean
- [runs/2026-11-08-b0-3-json-server.md](runs/2026-11-08-b0-3-json-server.md) — B0 run 3: Node/TS service hunt, clean
- [runs/2026-11-08-b0-4-live-flaskr.md](runs/2026-11-08-b0-4-live-flaskr.md) — B0 run 4: first live --target hunt, clean
- [runs/2026-11-08-b0-5-audit-realworld.md](runs/2026-11-08-b0-5-audit-realworld.md) — B0 run 5: first /audit, citation defects found
- [runs/2026-11-08-b0-6-audit-realworld-rerun.md](runs/2026-11-08-b0-6-audit-realworld-rerun.md) — B0 run 6: /audit rerun on both auth parts, clean
- [runs/2026-11-08-b0-7-python-markdown2-rerun.md](runs/2026-11-08-b0-7-python-markdown2-rerun.md) — B0 run 7: Python CLI rerun, home-path defect found
- [runs/2026-11-08-b0-8-json-server-service.md](runs/2026-11-08-b0-8-json-server-service.md) — B0 run 8: Node/TS hunt, leftover-process defect found
- [runs/2026-11-08-b0-9-godotenv-cmd.md](runs/2026-11-08-b0-9-godotenv-cmd.md) — B0 run 9: Go CLI hunt, clean
- [runs/2026-11-08-b0-10-json-server-adapters.md](runs/2026-11-08-b0-10-json-server-adapters.md) — B0 run 10: Node/TS hunt, leftover servers again
- [runs/2026-11-08-b0-11-godotenv-autoload.md](runs/2026-11-08-b0-11-godotenv-autoload.md) — B0 run 11: Go hunt, no bugs, clean
- [runs/2026-11-08-b0-12-live-flaskr-rerun.md](runs/2026-11-08-b0-12-live-flaskr-rerun.md) — B0 run 12: live rerun, clean; offline-only bug dropped
- [runs/2026-11-08-b0-13-json-server-adapters-rerun.md](runs/2026-11-08-b0-13-json-server-adapters-rerun.md) — B0 run 13: Node/TS hunt, verifier wrote into the repo
- [runs/2026-11-08-b0-14-live-flaskr-exit.md](runs/2026-11-08-b0-14-live-flaskr-exit.md) — B0 run 14: live hunt, clean
- [runs/2026-11-08-b0-15-audit-realworld-exit.md](runs/2026-11-08-b0-15-audit-realworld-exit.md) — B0 run 15: /audit, off-by-one citation confirmed (defect 10)
- [runs/2026-11-08-b0-16-json-server-adapters-exit.md](runs/2026-11-08-b0-16-json-server-adapters-exit.md) — B0 run 16: Node/TS hunt, clean
- [runs/2026-11-08-b0-17-live-flaskr-exit.md](runs/2026-11-08-b0-17-live-flaskr-exit.md) — B0 run 17: live hunt, clean
- [runs/2026-11-08-b0-18-audit-realworld-exit.md](runs/2026-11-08-b0-18-audit-realworld-exit.md) — B0 run 18: /audit, clean; B0 exit reached

## Features
-
