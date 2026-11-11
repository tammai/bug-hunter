# Close the open review tickets of lean scratch: sealed base, cache check, deep trees

## Why

**Request (verbatim):** "Fix the open review tickets of 2026-11-07-l-lean-scratch (released in v0.5.0) instead of filing issues: S6 (the --base copy source is writable and only its links are re-checked, so a change made during the hunt reaches the verifiers' copies), T2 (a base's .git can point git elsewhere through text, not links: config values, gitdir/commondir files), T3 (the isolate.py --cache marker check can raise instead of giving a one-line error), T6 (scratch.py clean's fd-based walk recurses and holds one handle per level, so a tree deeper than about 256 levels is left with an error and past ~1000 a traceback), plus L5 (misleading error text when _open_dir fails for a reason other than a link) and L6 (Windows top-level file that vanishes mid-clean reported as failure). … Windows-only behaviour can't be run here and stays recorded as a limit."

v0.5.0 gave every agent in a run a copy of one shared base clone (`$RUN/base`). The review of that change left tickets, and the owner wants them fixed, not filed. The one that matters is S6/T2: any agent can reach the base, and nothing notices when it changes, so a repro that edits, `git checkout`s or plants a hook or a `core.hooksPath` in the base changes the code every later copy runs. The rest are small: a traceback on an unsearchable cache parent, a deep tree that `clean` leaves behind, a wrong error message, and a Windows file that vanished reported as a failure.

**The user's words:** "so why dont fix now instead of a github issues?" and, mid-turn, "do all you can here, then a window pickup, push the branch, then i start a session on windows to finish". So: build and review here, hand the Windows checks and the shipping to a Windows session, and push the branch (no PR yet).

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| **Seal the base.** When `throwaway.py` makes a clone it writes `.git/bug-hunter-seal`: a SHA-256 over (1) the small files under `.git` (config, HEAD, hooks, info, refs, packed-refs, shallow, commondir and the like; not `objects/`, `index`, `logs/`, lock files or the two bug-hunter markers) and (2) the output of `git status --porcelain=v1 -z --ignored`. `--base` recomputes it and refuses a base whose seal differs. | Read-only base; hashing every file's contents; rewriting the copy's `.git/config` from a template | A read-only base would be copied read-only and need a chmod walk per copy. Hashing contents reads the whole repo per copy and throws away the copy-on-write saving. A rewritten config misses hooks and every other text file. `git status` is stat-based and cheap, and a base made dirty by line-ending settings still matches itself because the seal records what status said at birth. |
| The seal covers T2 (text pointers: `core.worktree`, `core.hooksPath`, `core.fsmonitor`, `url.*.insteadOf`, `commondir`, a hook). The existing `_git_points_out` check stays as the second line, on the copy. | Growing the config regex one key at a time | Any new config key a repro writes into `.git/config` changes the seal. |
| **Order of the checks (review S1):** the files digest is compared first, in pure Python; git runs on the base only after it matched, so a base whose config was changed is refused without running what it names. `git status` is also pinned (`core.fsmonitor`, `core.untrackedCache`, the global ignore and attributes files, submodules ignored), and the status digest includes `git ls-files -v` so `--skip-worktree` and `--assume-unchanged` are sealed (S2). The skips (`objects/`, `logs/`, `index`) apply at the top of `.git` only, and anything under `.git` that isn't a regular file refuses the base (L1, M2). The status digest is joined by a digest of the contents of every file git doesn't track, because the new files of the owner's uncommitted changes land in the base untracked and status lists them by name only (review TK1). `_git_points_out` also refuses `core.fsmonitor`, `core.hooksPath`, `filter.*.(clean|smudge|process)` and `diff.*.(textconv|command)` in `.git/config` outright (TK3), so those never reach the seal. | Comparing status first | Status executes a planted `core.fsmonitor` or filter before the mismatch is seen. |
| **Known limits:** code running as the same user can rewrite the seal file along with what it protects, so the seal catches accidents and a repro's ordinary side effects, not a repo written to defeat it. A change that exists only while `cp` runs (written and removed, or edited and reverted) passes both checks (S3). The contents of submodule folders are not sealed (`--ignore-submodules=all`, because status would run git inside them). The digest of `.git` reads whole files, including `modules/*/objects` and `lfs/objects` when a clone has them (cost only; left as a ticket, TK2). | A seal kept by another user or in a place agents can't write | Agents and the owner are one user, so there is nowhere else to keep it. Recorded, not fixed. |
| A base with no seal (made by v0.5.0) is refused with a one-line message to make a new one. | Trusting it | Fails closed; a run folder lives for one run, so a v0.5.0 base only meets this code mid-run across an upgrade. |
| **T3:** the `--cache` marker check uses `os.lstat` in a `try` and requires a regular file. Any failure is the existing one-line `error:` and exit 1. | `Path.is_file()` | `is_file()` raises `PermissionError` on 3.12 when the parent can't be searched, and follows a symlink named like the marker. |
| **T6:** `scratch.py clean` raises the soft open-file limit toward the hard limit and the recursion limit before it walks. A tree still too deep gives one error line and keeps the marker. | An iterative walk | The safe walk needs one open folder handle per level whatever the code looks like; the limits are what stops it, so they are what to raise. |
| **L5:** only the errors a swap produces (`ELOOP`, `ENOTDIR`, `ENOENT`) make `clean` unlink the entry. Any other failure to open a folder (too many open files, no permission) is recorded under its own message and the entry is left. | Unlinking on any error | Unlinking a real folder fails with "Is a directory", which hid the real cause. |
| **L6:** on Windows a top-level file that vanishes mid-clean is not an error. | Reporting it | Same as the nested case. |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** Given a base made by `throwaway.py`, when a tracked file in it is edited or deleted, an untracked or ignored file is added, or its `HEAD` or a ref is moved (a branch named like a skipped folder, `logs/main`, included), or a file is hidden with `--skip-worktree` or `--assume-unchanged` and then edited, then `throwaway.py <repo> <dest> --base <base>` refuses (exit 1, one `error:` line, no traceback, `dest` not created). An untouched base still copies, one that was already dirty when made (uncommitted changes, line-ending settings) still copies, and it copies whatever git ignore files the caller's `HOME` or `XDG_CONFIG_HOME` holds.
- **AC-002** Given the same base, when anything under its `.git` that git reads as text is changed after it was made (`config` gaining `core.hooksPath`, `core.fsmonitor` or a `url.*.insteadOf`, a `commondir` file, a file added to `hooks/`, `info/exclude`), then `--base` refuses the same way, without running any command the base names (`core.fsmonitor`, a clean filter), and a named pipe under `.git` is refused, not waited for.
- **AC-003** Given `isolate.py <scratch> --cache <cache>` where the cache's parent can't be searched, or the marker name is a symlink or a folder, then it stops with one `error:` line and exit 1, no traceback.
- **AC-004** Given a run holding a folder tree 600 levels deep (past macOS's default 256 open files and Python's default recursion limit), when `scratch.py clean` runs, then the run is removed and the exit is 0.
- **AC-005** Given a folder that can't be opened for a reason other than a swap (open files exhausted), when `clean` runs, then the error line names that reason ("Too many open files"), the folder is not unlinked, and the marker stays. A folder swapped for a link or file after it was listed is still removed as that entry.
- **AC-006** Given Windows' top-level clean, when a top-level file vanishes before it is removed, then that is not an error (`_clean_windows` is tested on every OS; running it on Windows is a manual check, see Out of scope).

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_throwaway.py › test_base_refuses_a_change_made_after_it_was_made; test_a_base_that_was_dirty_when_made_still_copies; test_index_flags_that_hide_edits_are_part_of_the_seal; test_the_seal_does_not_depend_on_the_callers_git_ignore_files; test_refs_named_like_skipped_folders_are_still_sealed | `uv run pytest tests/test_throwaway.py::test_base_refuses_a_change_made_after_it_was_made tests/test_throwaway.py::test_a_base_that_was_dirty_when_made_still_copies tests/test_throwaway.py::test_index_flags_that_hide_edits_are_part_of_the_seal tests/test_throwaway.py::test_the_seal_does_not_depend_on_the_callers_git_ignore_files tests/test_throwaway.py::test_refs_named_like_skipped_folders_are_still_sealed` |
| AC-002 | tests/test_throwaway.py › test_base_refuses_git_text_changed_after_it_was_made; test_a_planted_filter_is_refused_without_running; test_a_pipe_under_the_base_git_is_refused_not_waited_for | `uv run pytest tests/test_throwaway.py::test_base_refuses_git_text_changed_after_it_was_made tests/test_throwaway.py::test_a_planted_filter_is_refused_without_running tests/test_throwaway.py::test_a_pipe_under_the_base_git_is_refused_not_waited_for` |
| AC-003 | tests/test_isolate.py › test_cache_marker_check_never_raises | `uv run pytest tests/test_isolate.py::test_cache_marker_check_never_raises` |
| AC-004 | tests/test_scratch.py › test_clean_removes_a_tree_deeper_than_the_default_limits | `uv run pytest tests/test_scratch.py::test_clean_removes_a_tree_deeper_than_the_default_limits` |
| AC-005 | tests/test_scratch.py › test_clean_names_the_real_reason_when_a_folder_cant_be_opened | `uv run pytest tests/test_scratch.py::test_clean_names_the_real_reason_when_a_folder_cant_be_opened` |
| AC-006 | tests/test_scratch.py › test_windows_clean_ignores_a_top_level_file_that_vanishes | `uv run pytest tests/test_scratch.py::test_windows_clean_ignores_a_top_level_file_that_vanishes` |

## Must never break

- A copy never reaches back into the target; `--base` still copies with copy-on-write and reads none of the base's tracked file contents (the seal reads `.git`'s small files, `git status` and `ls-files`, which write nothing: `--no-optional-locks`, and the few untracked files of the owner's uncommitted changes).
- `scratch.py` never deletes anything outside the run or a folder it didn't make, and never follows a link (AC-006 of lean scratch). Raising limits changes how deep it can go, not what it follows.
- Isolation still fails closed: a refused cache or base stops the agent's command.
- A refused base says why in one line; a clean never ends in a traceback.

## Failure modes

- A base that is dirty at birth (line-ending conversion, file modes) → the seal records the dirty status, so it matches itself (AC-001).
- Agents copying while another agent's repro writes into the base → the seal is checked per copy, so a copy made after the write is refused; one made before it is a faithful copy of the base as it was (AC-001).
- Untrusted repo content writes git text into the base (hooks, config) → AC-002.
- Resource limits: open files and recursion depth on a deep tree → AC-004, AC-005.
- A cache parent that can't be searched → AC-003.
- A file removed by another process mid-clean on Windows → AC-006.

## Out of scope

- A seal agents can't rewrite (they run as the owner; recorded as a known limit above).
- Running the Windows-only behaviour here. A Windows session verifies: the junction test (`test_clean_removes_a_junction_without_entering_it`), `_clean_windows` with a real vanishing file, and that `--base` and the seal work with CRLF settings and without symlink rights. See `.sdlc/state/2026-11-09-m-scratch-tickets/windows-pickup.md`.
- Closing the Windows mid-clean junction swap (AC-006 of lean scratch stays narrowed there).
- Hashing the contents of the base's tracked files (only untracked ones are hashed; reading the whole repo per copy would cost what copy-on-write saves).

## Review

- **Recommended and chosen:** security and code (high depth), because the risk is high (untrusted repo content reaching git and file paths) and the track is M; chosen by the recommendation, the owner having said to do all that can be done on this machine.
- **Verdicts:** `.sdlc/.work/findings/2026-11-09-m-scratch-tickets/` (git-ignored)
  - Round 1: security-r1 FAIL (S1, S2; S3 low), code-reviewer-r1 FAIL (H1, M1, M2; L1 low)
  - Round 2: security-r2 FAIL (R2-1), code-reviewer-r2 FAIL (R2-1)
  - Round 3: security-r3 PASS, code-reviewer-r3 PASS
  - Round 3 ran on the owner's typed "one more round", as the round cap requires.
- **Fixed:**
  - S1: the seal's `git status` ran a planted `core.fsmonitor` or clean filter before refusing. The `.git` files digest is now compared first, in pure Python, and `_git_points_out` refuses those keys outright (`test_base_refuses_git_text_changed_after_it_was_made`, `test_a_planted_filter_is_refused_without_running`, `test_the_files_digest_is_checked_before_git_runs_on_the_base`; the first two assert a marker file was never created).
  - S2: `git ls-files -v` is part of the seal, so `--skip-worktree` and `--assume-unchanged` can't hide an edit (`test_index_flags_that_hide_edits_are_part_of_the_seal`).
  - H1: status is pinned against the caller's global ignore and attributes files (`test_the_seal_does_not_depend_on_the_callers_git_ignore_files`).
  - M1: the deep-tree test pins the soft open-file limit to 256 in the child, and fails without the raise (`test_clean_removes_a_tree_deeper_than_the_default_limits`).
  - M2: a pipe under `.git` is refused, not waited for (`test_a_pipe_under_the_base_git_is_refused_not_waited_for`).
  - L1, R2-1: skips apply only at the top of `.git`; proven by moving a ref with `commit-tree` and `update-ref` (`test_refs_named_like_skipped_folders_are_still_sealed`).
  - TK1: the contents of untracked files are hashed, because the owner's new files land in the base untracked (`test_a_file_that_was_untracked_in_the_base_at_birth_is_sealed_by_content`).
  - Mutation checks run by hand: removing the rlimit raise, the top-level-only rule, or the files-first order each makes its test fail.
- **Tickets:** TK2 (the `.git` digest reads whole files under `.git/modules/*/objects` and `lfs/objects`); S3-1 (`.git/config.worktree` is not scanned for the refused keys, and a partial-clone `uploadpack` lazy fetch needs a probe; the files digest still hashes `config.worktree`); S3-2 (the untracked digest has no type or length framing); T3-a (`lstat` then `open` of an untracked file can race); T3-b (an `init.templateDir` with a `config` setting a refused key would get every base refused at copy time, failing closed); T3-c (no test of its own for the smudge, process, textconv and diff-command keys); T3-d (an untracked file's mode isn't in the seal); S3 (a change that exists only while `cp` runs).
- **Drift and manual checks:**
  - Deviations in the state file: AC-001 and AC-002 widened after round 1; the round-2 fixes.
  - **Windows run, 2026-11-11** (Windows 11, Git Bash, uv's Python 3.13, Developer Mode on; per `windows-pickup.md`):
    - Full suite `uv run pytest`: 20 failed, 257 passed, 13 skipped; the 20 are exactly the rows of `.sdlc/baseline.md`, which grew by three with the owner's OK (two tests whose committed symlink Git for Windows checks out as a plain file, `core.symlinks=false`; `scratch.py clean` can't remove a read-only folder on Windows, a v0.5.0 bug filed in `docs/sdlc/todo.md`). All three fail identically on `main`. Lint passes.
    - `test_clean_removes_a_junction_without_entering_it`: ran, passed (first run anywhere).
    - AC-006, `test_windows_clean_ignores_a_top_level_file_that_vanishes`: passed. The optional live timing check (item 5) was not done.
    - **Found and fixed: the seal missed an edit to the base on Windows** (`test_base_refuses_a_change_made_after_it_was_made`, edit case, copied). Cause: the clone checks out with Git for Windows' system `core.autocrlf=true`, the pinned status hides the system config, so every text file reads ` M` at birth, and status names a path, not its contents. The same hole held on every platform for any file the owner's uncommitted changes touched. Fix: the seal hashes the contents of every path the pinned status lists (changed, deleted as a sentinel, untracked, ignored); new test `test_a_file_that_was_changed_in_the_base_at_birth_is_sealed_by_content` (edit, re-created deletion, force-added ignored file), red then green. Deviations logged. This fix came after round 3 and has not been reviewed yet.
    - `core.excludesFile=nul` / `core.attributesFile=nul`: read as empty (`test_the_seal_does_not_depend_on_the_callers_git_ignore_files` passes).
    - `core.autocrlf true` with a base made from a dirty repo: copies (`test_a_base_that_was_dirty_when_made_still_copies` passes).
    - `touch` on the Git Bash PATH: a control repo with `core.fsmonitor=touch ran-marker` created the marker on `git status`, so the fsmonitor and filter tests pass for the right reason.
    - Reading `.git` while git holds a file open: no "changed after it was made" on an untouched base in any run.
    - AC-003 by hand: `.bug-hunter-run` as a folder, and no marker, each print one `error:` line and exit 1, no traceback.
    - Junction swapped mid-clean (item 6): known limit, not tried.
    - Not met here: `verify.py` can't pass on this clone: the red runs are in the Mac's git-ignored `.sdlc/.work/`, and the AC-003, AC-004 and AC-005 tests are POSIX-only (skip on Windows). The new test is named here, not yet in AC-001's row.
  - CI (Ubuntu) runs on the PR.
- **Security:** the two reviews above; no dependency was added or changed (standard library only), so no dependency audit ran.
- **Lessons filed:** `knowledge/gotchas/copying-a-target-repo.md` (the sealed base and its limits) and one line in `docs/sdlc/recurring-defects.md`.
