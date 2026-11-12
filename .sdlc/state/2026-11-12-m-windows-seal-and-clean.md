# 2026-11-12-m-windows-seal-and-clean
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-12-m-windows-seal-and-clean.md   (this feature's record for people)
Track: M   (sized up because: four code files across two scripts and their tests; footprint: 6 files)
Risk: high   (untrusted run content reaching file deletion and chmod; the base seal)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-12
Base: 202a2b6
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 202a2b6 tree d5edff9d0ebf2e3aad1e846f9374e7ae319b5f73
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part; the Windows checks (AC-004) in a short Windows session at the end

## Handoff
- autocrlf/eol: in _make right after the clone and origin removal, before the diff apply and _seal (scripts/throwaway.py _make)
- read-only folders: _clear_read_only scripts/scratch.py:83 skips folders; _remove_tree_windows retry scripts/scratch.py:170

## Tasks
1. **Line-ending keys in the clone** — AC-001
   - Files: `scripts/throwaway.py`, `tests/test_throwaway.py`
2. **Clear read-only folders on Windows clean** — AC-002 AC-003
   - Files: `scripts/scratch.py`, `tests/test_scratch.py`
3. **Windows run and baseline** — AC-004
   - Files: `.sdlc/baseline.md`, `docs/sdlc/todo.md`

## Public Surface
- none

## Test lock
- `tests/test_scratch.py` sha256:61173f9b56927baf084358203f1976f029a9575bdb6ce293608ccae2215d3f2a
- `tests/test_throwaway.py` sha256:20c566c6c1a1775b8b211ee9a09cc2942c15f84ca8bee1b8c0cf0e03906581d4

## Gate log
- 2026-11-12 Stage 1: pass — approved by the owner (high-risk M)
- 2026-11-12 Stage 2: pass — verify PASS; AC-004 manual (Windows)
- 2026-11-12 review: round 1, security and code (Risk: high), chosen by the owner
- 2026-11-12 Stage 3: fail — round 1: code FAIL C1-1, C1-3, C1-4 (high), C1-5, C1-7, C1-6; security PASS with S-1, S-2 unconfirmed (same classes)
- 2026-11-12 Stage 2: pass — round 1 fixes; verify PASS
- 2026-11-12 review: round 2 closing check, code review on the round 1 fixes (security passed round 1)
- 2026-11-12 Stage 2: pass — round 2 mediums fixed; verify PASS
- 2026-11-12 Stage 3: pass — security-r1 PASS, code-reviewer-r2 PASS; round 2 mediums fixed and verified; AC-004 waits for Windows
- 2026-11-12 AC-004 (manual, Windows): pass at 86398d4 — full suite 19 failed, all baseline rows; read-only clean test passes and its baseline row is removed; base has core.autocrlf=true, empty pinned status, --base copy after plain git status exits 0

## Deviations
- 2026-11-12 task 3 (Windows run and baseline) What: not done on macOS; .sdlc/baseline.md and docs/sdlc/todo.md are unchanged. Why: AC-004 needs Windows (the real rmdir refusal and Git for Windows' system autocrlf). Effect: a Windows session runs the full suite and the base check, then removes the read-only row from the baseline and ticks the todo; until then the row stays.
- 2026-11-12 scripts/throwaway.py, scripts/scratch.py round 1 fixes. What: line endings read typed and passed to git clone --config (C1-1, C1-8); _git drops git's repo-locating variables on every call (C1-3, S-2); _clear_read_only skips any reparse point and never follows a link (fchmod on an O_NOFOLLOW descriptor on POSIX, follow_symlinks=False on Windows), and the parent-folder clear is gone (C1-4, C1-5, S-1); stale _seal_git comment (C1-6); the eol case gets * text=auto (C1-7). Why: review round 1. Effect: the AC-002 and AC-003 tests apply Windows' write-bit rule to unlink and rmdir and run on every OS; AC-003 adds a swapped-link case; new test test_a_copy_ignores_the_callers_git_repo_variables; Decisions and AC-002/AC-003 text amended.
- 2026-11-12 test-change tests/test_throwaway.py What: AC-001's test gains the bare-key, 2 and input cases and * text=auto for the eol case; test_a_copy_ignores_the_callers_git_repo_variables added. Why: review round 1 (C1-1: values git reads as true weren't recorded; C1-7: the eol case couldn't fail; C1-3). test-change tests/test_scratch.py What: AC-002 and AC-003 apply Windows' write-bit rule to unlink and rmdir; AC-003 adds a swapped-link case and a read-only folder of the run's own. Why: C1-4, C1-5, S-1.
- 2026-11-12 scripts/scratch.py _clear_read_only, round 2 mediums. What: one chmod path, with follow_symlinks=False where supported, replaces the Windows/POSIX split (C2-4, C2-8); only name-surrogate reparse points are skipped, so dedup and cloud placeholder files are cleared (C2-3); files get read and write; the comment names the known limit (C2-1). test-change tests/test_scratch.py What: the swap case gives the file link a file's stat and runs where chmod can refuse to follow (C2-7); new test test_windows_clear_read_only_skips_only_links_among_reparse_points, red then green. Why: review round 2 (PASS) listed them; closed by verify.

## Open questions
-
