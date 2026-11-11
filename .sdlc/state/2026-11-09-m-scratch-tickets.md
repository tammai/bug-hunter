# 2026-11-09-m-scratch-tickets
Status: done
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
Verified: c766c38 tree 695f6711aa6cb48225d6503457018ed09cfc6eb1
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
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
- 2026-11-11 macOS: AC-001 row gains test_a_file_that_was_changed_in_the_base_at_birth_is_sealed_by_content; verify.py red --at 4328dfa AC-001 recorded red; the new test also fails on macOS against the round-3 seal (648fd0e: edit to a born-dirty file copied, exit 0), so the hole was cross-platform; verify PASS head c766c38 tree 17073f7b
- 2026-11-11 Stage 2: pass — Windows seal fix built; AC-001 red at Base, verify PASS
- 2026-11-11 review: round 4, ran security and code (Risk: high) on git diff 648fd0e -- scripts/throwaway.py tests/test_throwaway.py, chosen by the owner's typed 'OK, run both reviews'
- 2026-11-11 Stage 3: fail — round 4: code-reviewer FAIL C4-1 (high) plus medium bugs C4-2..C4-5; security PASS with lows
- 2026-11-11 Stage 2: pass — round 4 fixes: C4-1..C4-5, S4-2, S4-4, T4-a; verify PASS
- 2026-11-11 review: round 5 closing check, code review only (security passed round 4), on the owner's typed 'one more round'
- 2026-11-11 Stage 3: fail — round 5 closing check FAIL R5-1, R5-3 (high), R5-5 medium; owner chose the whole-tree walk
- 2026-11-11 Stage 2: pass — round 5 fixes: whole-tree walk; verify PASS
- 2026-11-11 review: round 6 closing check, code review on the uncommitted fixes, on the owner's typed 'one more round, whole-tree walk'
- 2026-11-11 Stage 3: fail — round 6 closing check FAIL R6-2 (high), R6-1 medium; owner typed 'one more round'
- 2026-11-11 Stage 2: pass — round 6 fixes R6-1, R6-2; verify PASS
- 2026-11-11 review: round 7 closing check, code review on R6-1 and R6-2 fixes, on the owner's typed 'one more round'
- 2026-11-11 Stage 3: pass — security-r4 PASS, code-reviewer-r7 PASS; R7-6 fixed and verified; Learn: three recurring defects, gotcha updated

## Deviations
- 2026-11-09 2026-11-09 AC-001 and AC-002 widened after review round 1. What: AC-001 also covers moved refs, skip-worktree and assume-unchanged edits and the caller's global ignore files; AC-002 also covers not running a planted fsmonitor or filter and a named pipe under .git; the seal is now a files digest compared before git runs plus a pinned status digest. Why: security S1 (the first seal ran the base's fsmonitor before refusing), S2, and code H1, M2, L1. Effect: tests/test_throwaway.py gains six tests, scripts/throwaway.py changes only the seal; S3 and submodule contents are recorded as known limits.
- 2026-11-09 2026-11-09 round 2 fixes after the owner's typed 'one more round'. What: the seal now also hashes the contents of untracked files (TK1), config keys core.fsmonitor, core.hooksPath, filter.* and diff.*.textconv are refused outright in .git/config (TK3), the L1 test moves the ref without git commit (R2-1). Why: security-r2 tickets TK1 and TK3 and code R2-1. Effect: scripts/throwaway.py seal gains a third digest and a stricter config check; two tests' expected refusal message changed to the earlier, more specific one, and a unit test now pins the files-before-git order; TK2 (cost of reading whole files under .git/modules and lfs) stays a ticket.
- 2026-11-11 2026-11-11 scripts/throwaway.py seal, Windows run. What: the seal now hashes the contents of every path the pinned status lists (changed, deleted as a sentinel, untracked), not only untracked files; status and index flags are read once (_seal_git). Why: on Windows test_base_refuses_a_change_made_after_it_was_made failed (edit case copied): the clone checks out with the system core.autocrlf=true, the pinned status hides it, so every text file reads ' M' at birth and a later edit leaves status unchanged; the same hole held on every platform for files the owner's uncommitted changes touched. Effect: new test test_a_file_that_was_changed_in_the_base_at_birth_is_sealed_by_content (red, then green); bases made before this change are refused as changed; on Windows each copy reads every text file of the base (cost, like TK2).
- 2026-11-11 2026-11-11 .sdlc/baseline.md and docs/sdlc/todo.md, baseline grown with the owner's OK. What: three Windows-only rows added (test_copy_from_a_base_is_independent_and_checked, test_copy_from_a_base_falls_back_when_cp_fails: Git for Windows core.symlinks=false checks links out as files; test_clean_reports_size_and_removes_read_only_trees: scratch.py clean can't remove a read-only folder on Windows, a real v0.5.0 bug, filed as a todo) and the reason on test_refuses_symlinks_out_of_the_copy_and_a_used_dest updated. Why: with Developer Mode on they still fail on Windows, identically on main, so this change didn't cause them. Effect: Review gates on the grown baseline; the read-only clean fix is its own S change.
- 2026-11-11 2026-11-11 scripts/throwaway.py seal, correction to the line before: the content digest covers every path the pinned status lists, ignored ones included (status --ignored), so a file the owner force-added (git add -f) but didn't commit, which lands in the base ignored, stays sealed by content as git ls-files -o sealed it before. Test: the ignored case in test_a_file_that_was_changed_in_the_base_at_birth_is_sealed_by_content, red then green.
- 2026-11-11 2026-11-11 scripts/throwaway.py seal, round 4 fixes. What: one _hash_entry for .git files and status-listed paths, each entry length-framed with a type tag, mode and a per-file content hash, opened O_NOFOLLOW|O_NONBLOCK and checked with fstat (C4-2, C4-3, C4-4, C4-7, S4-1, S4-2, tickets S3-2, T3-d, T3-a); a path deleted under a folder now a file is sealed as deleted, not a failure (C4-1, high); _pinned drops the caller's GIT_* variables (T4-a); a name Windows can't decode is a one-line refusal (S4-4). Why: round 4 code review FAIL C4-1, mediums fixed by the rule. Effect: every base made before is refused (the .git digest format changed); AC-001 gains test_a_base_born_with_a_folder_turned_into_a_file_still_copies and test_the_seal_does_not_depend_on_the_callers_git_environment; the born-dirty test copies an untouched base first and adds shift, mode and link cases; the change file's Must never break, Out of scope and Decisions text amended with the owner's typed OK (S4-3).
- 2026-11-11 2026-11-11 scripts/throwaway.py seal, round 5 fixes, the owner's typed choice of the whole-tree walk. What: _seal_tree, a pure-Python walk of the whole working tree between the .git files digest and git (name, type, mode, size, mtime of every entry; a .git in any case below the top, a pipe or a device refuses); _hash_entry seals a folder at a listed path as a folder; the seal has four lines. Why: round 5 R5-1 (planted src/.git reaching the owner's repo, high), R5-3 (file turned into a folder at birth, high), R5-5 (pipe and empty folder unseen). Effect: AC-001 gains test_a_base_born_with_a_file_turned_into_a_folder_still_copies and test_what_git_status_never_lists_is_still_sealed, AC-002 gains test_a_git_planted_below_the_top_of_the_base_is_refused; the Decisions rows and knowledge/gotchas/copying-a-target-repo.md describe the walk; submodule folders' files are now sealed by name, size and mtime; every earlier base is refused.
- 2026-11-11 2026-11-11 scripts/throwaway.py, round 6 fixes. What: _seal_files encodes names with os.fsencode and both pure-Python walks treat ValueError like OSError (R6-2, high); _git_points_out runs git config from the temp folder like _git (R6-1). Why: round 6 closing check. Effect: tests test_a_name_under_git_that_isnt_utf8_is_sealed_not_a_traceback (must-never-break: one line, no traceback) and test_a_copy_from_a_deleted_current_folder_still_copies, each red then green; no AC row changed.
- 2026-11-11 2026-11-11 scripts/throwaway.py _main, round 7 medium R7-6. What: a deleted current folder with relative paths is one line naming that, not 'git is not installed'; _main uses the absolute dest after. Why: round 7 (PASS) listed it, the rest of R6-1's class. Effect: test_a_copy_from_a_deleted_current_folder_still_copies gains the relative case, red then green; closed by verify without another round.

## Open questions
-
