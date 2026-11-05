# Part plan: bug-hunter plugin v1 B2

**Record:** `docs/sdlc/changes/2026-11-05-l-hunt-plugin.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **Fake `gh` fixture** — AC-004
   - Files: `tests/conftest.py`
   - Then: a `gh` script on PATH that logs each call and answers `auth status`, `issue list` and `issue create` from env vars (reused by B3).
2. **known.py** — AC-004
   - Files: `scripts/known.py`, `tests/test_known.py`
   - Test first: `test_lists_open_issues_and_earlier_drafts`.
   - Then: `gh issue list` JSON plus earlier drafts' titles as markdown; any `gh` failure becomes an "unavailable (why)" line, exit 0.
3. **drafts.py** — AC-005, AC-006, AC-007
   - Files: `scripts/drafts.py`, `tests/test_drafts.py`
   - Test first: the three AC tests in `tests/test_drafts.py`.
   - Then: `dir` (from `origin`), `next` (numeric max + 1 over `NN.md`), `check` (title, four sections in order, non-empty, a code block in Steps); `title()` and `numbered()` are reused by `known.py` and B3's `post.py`.

## Public Surface

- `scripts/known.py <repo> <drafts-dir>` — AC-004
- `scripts/drafts.py dir <repo> | next <dir> | check <file>` — AC-005, AC-006, AC-007
