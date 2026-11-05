---
type: decision
title: Drafts live outside the target, one folder per origin URL part
description: Where /hunt writes drafts and posted.json, and why that layout.
---

# Drafts live outside the target

**Decision (2026-11-05):** a repo's drafts and `posted.json` go in `~/.bug-hunter/<host>/<owner>/<repo>/drafts/` (every path part of `origin`, so GitLab subgroups nest too), or in `~/.bug-hunter/local/<folder>/drafts/` when there's no `origin`. `scripts/drafts.py dir` is the only place that computes it.

**Why:**
- Constitution III: hunting leaves nothing in the target.
- The same folder holds earlier findings, so later runs skip them.
- One folder level per URL part: joining with `-` made `acme-web/api` and `acme/web-api` share a folder, so one repo's drafts were offered, and `posted.json` skipped, in another. A `.` or `..` part is refused, so the path can't climb out.

**Ruled out:** `drafts/` in the target; `<owner>-<repo>` names.

From [2026-11-05-l-hunt-plugin](../../docs/sdlc/changes/2026-11-05-l-hunt-plugin.md).
