# 2026-11-09-m-scratch-tickets
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-09-m-scratch-tickets.md   (this feature's record for people)
Track: M   (sized up because: seven files across three scripts and their tests; footprint 7; footprint: 7 files)
Risk: high   (untrusted repo content (git config, hooks, deep trees) reaching git and file paths; isolation)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-09
Base: 4328dfa
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 4328dfa tree 4429c53b2d5b2dc12eb51982efe0c4c627e597b3
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part; Windows-only checks and shipping are left to a Windows session (windows-pickup.md)

## Handoff
- seal lives in .git/bug-hunter-seal; _copy_base in scripts/throwaway.py recomputes it; the marker .git/bug-hunter-base stays as is
- scratch.py clean: _open_dir/_remove_dir/_empty_dir (POSIX fd walk) and _clean_windows; limits raised once at the top of the POSIX clean
- isolate.py cache marker check is the Path.is_file() call near the --cache parsing

## Tasks
1. **Seal the base** — AC-001 AC-002
   - Files: `scripts/throwaway.py`, `tests/test_throwaway.py`, `knowledge/gotchas/copying-a-target-repo.md`
2. **Cache marker check never raises** — AC-003
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
3. **Clean: deep trees, real error reasons, Windows vanish** — AC-004 AC-005 AC-006
   - Files: `scripts/scratch.py`, `tests/test_scratch.py`

## Public Surface
- none

## Gate log
- 2026-11-09 Stage 1: pass — plan not stopped for approval: the owner said 'do all you can here' and will finish on Windows
- 2026-11-09 Stage 2: pass — built; verify pass; AC-001 to AC-006 green

## Deviations
- 2026-11-09 2026-11-09 AC-001 and AC-002 widened after review round 1. What: AC-001 also covers moved refs, skip-worktree and assume-unchanged edits and the caller's global ignore files; AC-002 also covers not running a planted fsmonitor or filter and a named pipe under .git; the seal is now a files digest compared before git runs plus a pinned status digest. Why: security S1 (the first seal ran the base's fsmonitor before refusing), S2, and code H1, M2, L1. Effect: tests/test_throwaway.py gains six tests, scripts/throwaway.py changes only the seal; S3 and submodule contents are recorded as known limits.
- 2026-11-09 2026-11-09 round 2 fixes after the owner's typed 'one more round'. What: the seal now also hashes the contents of untracked files (TK1), config keys core.fsmonitor, core.hooksPath, filter.* and diff.*.textconv are refused outright in .git/config (TK3), the L1 test moves the ref without git commit (R2-1). Why: security-r2 tickets TK1 and TK3 and code R2-1. Effect: scripts/throwaway.py seal gains a third digest and a stricter config check; two tests' expected refusal message changed to the earlier, more specific one, and a unit test now pins the files-before-git order; TK2 (cost of reading whole files under .git/modules and lfs) stays a ticket.

## Open questions
-
