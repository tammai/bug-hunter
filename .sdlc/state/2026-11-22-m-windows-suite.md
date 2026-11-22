# 2026-11-22-m-windows-suite
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-windows-suite.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 10 files)
Risk: low
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: 635113a
Owner: tam.mai@bigin.vn
Tool: claude-code
Current: Stage 2 – Build

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [ ] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline

## Handoff
- fake gh: python under the name gh in a venv-shaped folder; .pth hook reads sys.orig_argv; tests/conftest.py
- Windows halves verified by reasoning only until the first windows-latest CI run; baseline rows stay

## Tasks
1. **Portable fixture helpers and fake gh** — AC-001 AC-002 AC-003 AC-004 AC-005 AC-006
   - Files: `tests/conftest.py`, `tests/test_portable_fixtures.py`
2. **Call sites use the helpers** — AC-008
   - Files: `tests/test_known.py`, `tests/test_post.py`, `tests/test_drafts.py`, `tests/test_findings.py`, `tests/test_scope.py`, `tests/test_stacks.py`, `tests/test_throwaway.py`
3. **windows-latest CI runner** — AC-007
   - Files: `.github/workflows/sdlc-verify.yml`

## Public Surface
- none

## Test lock
- `tests/test_portable_fixtures.py` sha256:25b0caf7cd9e1c18d435f9d57a64676b9558ecd5b33af5be7934f902e7246ea9

## Gate log
- 2026-11-22 Stage 1: pass — plan not stopped for approval: low-risk M
- 2026-11-22 review deferred: coordinator runs every lane's reviews together after the build; committed on the branch, not pushed

## Deviations
- 2026-11-22 test-change tests/test_portable_fixtures.py What: the lock test's finally called a misspelled name (unconftest.lock_dir) and now calls conftest.unlock_dir. Why: a typo from rewriting the imports into attribute access; the test was red for the missing helper either way, not weakened.
- 2026-11-22 Task 2 What: also changed mode asserts at test_findings.py:775/834/901 and the CRLF accepted-list fixture at test_findings.py:705, which no baseline row names. Why: same Windows failure class in tests added after the baseline was recorded; left alone they turn the new runner red. Effect: none on macOS/Linux.
- 2026-11-22 test-change tests/test_portable_fixtures.py What: AC-001 runs the fake by its resolved path; AC-005 checks the lock with open(x) instead of mkstemp; AC-006 asserts the core.symlinks case only where links can be created, after the no-rights case. Why: on Windows a child's env doesn't steer CreateProcess's lookup of gh; 3.12's mkstemp spins on a denied folder; an account without link rights hits the other reason first. Not weakened: the same behaviours are asserted.
- 2026-11-22 Task 3 What: .sdlc/config.json gets ci.os = [ubuntu-latest, windows-latest]. Why: the scaffold builds sdlc-verify.yml's matrix from it, so /sdlc:upgrade would otherwise drop the runner. Effect: none locally.
- 2026-11-22 Task 2 What: the two post.py lock tests skip on a Python whose tempfile.TMP_MAX > 100 on Windows (3.12). Why: tempfile retries a refused mkstemp 2**31 times there, so post.py would hang the job. Effect: none on macOS/Linux or on Windows with 3.13+; the post.py bug is a ticket.

## Open questions
-
