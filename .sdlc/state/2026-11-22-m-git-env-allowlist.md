# 2026-11-22-m-git-env-allowlist
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-git-env-allowlist.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 6 files)
Risk: high   (secrets: agent isolation boundary; untrusted environment input)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: 35c520c
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 35c520c tree 9c3b193de5728041cb15915ebe3c7cb7aa46b202
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline in this session; a short Windows session at the end runs the Windows-only checks

## Handoff
- unset set is built in _plan: scripts/isolate.py:219-225; exported names are never unset, so the allowlist is exports plus KEEP_IF_SET
- _win_path strips quotes then whitespace in the wrong order: scripts/isolate.py:80
- _is_link + is_dir make 3 stat calls per level: scripts/isolate.py:263-283
- print of the shell line is the only stdout write: scripts/isolate.py:533
- PATH guard: tests/conftest.py:29-35; test_post.py:133 asserts every gh folder also holds git

## Tasks
1. **GIT_* allowlist and SSH_ASKPASS** — AC-001 AC-002 AC-003
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
2. **Windows path matching: short names, whitespace in quotes** — AC-004 AC-005
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
3. **One-line error for an unencodable value; fix the skip reason** — AC-006
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
4. **One lstat per level in the path fallback** — AC-007
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
5. **Narrow the test gh guard on POSIX** — AC-008
   - Files: `tests/conftest.py`, `tests/test_post.py`
6. **Docs and todo** — AC-001 AC-007
   - Files: `knowledge/gotchas/isolating-agents-without-a-sandbox.md`, `docs/sdlc/todo.md`

## Public Surface
- none

## Test lock
- `tests/test_isolate.py` sha256:9dc23fd43d1ca404d4f27e0f56b52ab11511081e632441352438d992584f1be7
- `tests/test_post.py` sha256:003af65f372718dda6172f7077be484916c2d553f59013c2a3ea95c54a5f3a9b

## Gate log
- 2026-11-22 Stage 1: pass — plan approved by the owner (high-risk M)
- 2026-11-22 Stage 2: pass
- 2026-11-22 review: security + code (Risk: high), chosen by the owner
- 2026-11-22 Stage 2: pass
- 2026-11-22 Stage 2: pass
- 2026-11-22 Stage 3: pass

## Deviations
- 2026-11-22 tests/test_isolate.py What: AC-002 shares AC-001's test (test_every_inherited_git_override_is_dropped) instead of its own. Why: the allowlist already survives today, so a test of its own couldn't fail first. Effect: one test proves both; its row in the change file names that test.
- 2026-11-22 test-change tests/test_post.py What: import order only (ruff I001 wanted import pytest grouped with the conftest imports). Why: lint failed in verify. Effect: no test behaviour changes.
- 2026-11-22 test-change tests/test_isolate.py What: AC-001's test allows GIT_EDITOR and GIT_PAGER and asserts their values (true, cat); four new tests for review round 1 (editor/pager, no ctypes, error names the inherited variable, long-name walk and UNC skip). Why: review round 1 CR1/CR2/CR3/CR6 and security S1; isolation now exports its own GIT_EDITOR and GIT_PAGER. Effect: stricter, not weaker.
- 2026-11-22 test-change tests/test_post.py What: the gh invariant also asserts no gh on PATH at all on POSIX. Why: security S3, the old assert accepted the weaker guard. Effect: stricter.
- 2026-11-22 tests/conftest.py What: gh_free_path asserts its shim holds no gh. Why: security S3. Effect: the session fails at startup instead of reaching a real gh.
- 2026-11-22 test-change tests/test_isolate.py tests/test_post.py What: review round 2: the no-ctypes test skips on Windows; the encoding-error test adds an unset secret beside an exported bad value; the long-name test adds \??\ and a mapped network drive; the gh guard test adds a relative PATH entry. Why: round 2 findings on this change's own code. Effect: stricter, nothing removed.

## Open questions
-
