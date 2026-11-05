# Part plan: bug-hunter plugin v1 B3

**Record:** `docs/sdlc/changes/2026-11-05-l-hunt-plugin.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **post.py** — AC-008, AC-009
   - Files: `scripts/post.py`, `tests/test_post.py`
   - Test first: `test_files_named_drafts_once`, `test_refuses_before_filing_and_keeps_partial_progress` (fake `gh` from B2's fixture).
   - Then: resolve numbers to `NN.md` via `drafts.numbered`, check each with `drafts.problems`, `gh auth status`, then `gh issue create` per draft as an argument list, writing `posted.json` after each one (temp file + replace).
2. **/hunt-post** — AC-012
   - Files: `commands/hunt-post.md`, `tests/test_plugin_files.py`
   - Test first: `test_hunt_post_files_only_through_post_script`.
   - Then: the command finds the drafts folder, shows the named drafts, asks for the label when none is given, and runs `post.py`.

## Public Surface

- `scripts/post.py <drafts-dir> <numbers…> --label <label>` — AC-008, AC-009
- `/hunt-post <numbers…> [--label <label>]` — AC-012
