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

## Runbooks
- [runbooks/release.md](runbooks/release.md) — how to cut, smoke-test and roll back a release

## Features
-
