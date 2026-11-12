# Windows: a base sealed without reading every text file, and clean that removes read-only folders

## Why

**Request (verbatim):** "Fix two Windows tickets: (1) the base seal re-reads most text files on every copy on Windows because the pinned status drops the system core.autocrlf the clone was checked out with — record the clone's effective core.autocrlf/core.eol in its own .git/config at birth so the pinned status agrees with the checkout (tickets C4-6/R6-5/R6-7/R7-2 in docs/sdlc/changes/2026-11-09-m-scratch-tickets.md); (2) scratch.py clean on Windows can't remove a read-only folder such as Go's module cache (docs/sdlc/todo.md; baseline row tests/test_scratch.py › test_clean_reports_size_and_removes_read_only_trees). Build and test on macOS; a short Windows run confirms at the end."

Both are left over from [2026-11-09-m-scratch-tickets](2026-11-09-m-scratch-tickets.md) and only bite on Windows, where every hunt runs `throwaway.py` per agent and `scratch.py clean` once per run.

**1. The seal reads most of the repo on Windows.** `throwaway.py` clones with the caller's git config, so on Git for Windows the system `core.autocrlf=true` checks text files out with CRLF. The seal then reads the base through a status pinned against system and global config (`_pinned`: `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL=nul`), which sees LF in the index and CRLF on disk. Every text file git has to compare (racily clean after the clone) reads as changed, so the content digest reads and hashes nearly every text file at birth and twice per copy, and a plain `git status` run in the base refreshes the index, changes the pinned listing and gets the base falsely refused (R6-5).
- **Root cause:** the checkout and the pinned status disagree on line endings. Recording the effective `core.autocrlf` and `core.eol` in the clone's own `.git/config` (which the pinned status does read, and the seal covers) makes them agree, so status lists only real changes.

**2. Clean can't remove a read-only folder on Windows.** Found by the 2026-11-11 Windows run: `test_clean_reports_size_and_removes_read_only_trees` fails with "Access is denied" on `hunter-1/home/go/pkg/mod/example.com@v1` (Go makes its module cache read-only, 0555), on `main` too, so a hunt's run folder is left partly behind.
- **Root cause:** `_clear_read_only` (`scripts/scratch.py:83`) clears the read-only attribute only on regular files. Windows refuses `rmdir` on a folder that has it, and `_remove_tree_windows`'s retry calls `_clear_read_only`, which skips folders, so the retry fails the same way.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Before the clone, read `core.autocrlf` and `core.eol` with the caller's config (the config the checkout uses), typed as git reads them (a bare key or `2` is `true`; `input` kept), and pass each one that is set to `git clone --config`, so the checkout and the clone's own `.git/config` agree by construction, before the owner's diff and the seal (review round 1, C1-1, C1-8). | Clone with `-c core.autocrlf=false`; let the pinned status read system config | A forced `false` would hand agents LF files on Windows where the owner's tools expect CRLF, changing what a repro sees. Reading system config again brings back what pinning exists to keep out (the caller differs between orchestrator and agent). Copies made with `--base` inherit the setting with `.git/config`. |
| Only those two keys. | Copying the whole effective config | Both decide how text is checked out; everything else is either written by the clone itself (`core.filemode`, `core.symlinks`, `core.ignorecase`) or must not reach the copy. |
| `_clear_read_only` also clears a folder's read-only attribute (`S_IRWXU`; on Windows only the write bit matters), for the entry the retry in `_remove_tree_windows` couldn't remove and nothing else. Never through a link: it skips any Windows reparse point (`FILE_ATTRIBUTE_REPARSE_POINT`, not only junctions) and changes the mode with `follow_symlinks=False` on Windows, and through an `O_NOFOLLOW` descriptor (`fchmod`) on POSIX, so a link swapped in after the check is not followed (review round 1, C1-4, S-1). The tests apply Windows' rule (an entry without its write bit can't be removed) to `unlink` and `rmdir`, so they run on every OS. | Chmod the whole tree first; also clearing the parent folder | One pass, and only what failed. Clearing the parent is a POSIX rule Windows doesn't have, and it changed a folder by a path an ancestor swap could redirect (C1-4, C1-5). |
| Every git command `throwaway.py` runs drops the variables `git rev-parse --local-env-vars` lists (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, …), keeping `GIT_CONFIG_GLOBAL` and the rest the agents run with. | Dropping every `GIT_*` variable | Set inside a hook or alias of another repo, those send the clone, the origin removal and the patch to that repo (review round 1, C1-3, S-2; it held before this change). Dropping the config variables too would bring back the line-ending mismatch. |
| The baseline row stays until the Windows run shows it passing. | Removing it now | The real failure only exists on Windows. |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** Given a caller whose git config sets `core.autocrlf` (and one that sets `core.eol`), when `throwaway.py` makes a base, then the base's own `.git/config` holds the same value; and the pinned status of the untouched base lists no tracked file even when git must compare contents (files' modification times moved), so a `--base` copy of it succeeds. A caller that sets neither gets neither written.
- **AC-002** Given Windows' rule that an entry without its write bit can't be removed, and a run tree holding a read-only folder and a read-only file (Go's module cache), when `_remove_tree_windows` removes it, then the tree is gone and no error is recorded. Runs on every OS.
- **AC-003** Given links under the run that point at a read-only folder and file outside it, including a link swapped in after the check saw a folder, when Windows' clean clears read-only and removes the tree, then the outside folder's and file's modes and contents are unchanged. Runs on every OS that can make a symlink.
- **AC-004** (manual, Windows) On Windows, `tests/test_scratch.py › test_clean_reports_size_and_removes_read_only_trees` passes and its row leaves `.sdlc/baseline.md`; a base made there has an empty pinned status and is not refused after a plain `git status` in it.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_throwaway.py › test_a_base_records_the_line_ending_settings_it_was_checked_out_with | `uv run pytest tests/test_throwaway.py::test_a_base_records_the_line_ending_settings_it_was_checked_out_with` |
| AC-002 | tests/test_scratch.py › test_windows_tree_removal_clears_read_only_folders | `uv run pytest tests/test_scratch.py::test_windows_tree_removal_clears_read_only_folders` |
| AC-003 | tests/test_scratch.py › test_windows_tree_removal_never_changes_modes_through_a_link | `uv run pytest tests/test_scratch.py::test_windows_tree_removal_never_changes_modes_through_a_link` |
| AC-004 | manual | Windows only: the real `rmdir` refusal and Git for Windows' system `autocrlf` can't be reproduced on macOS. Run on Windows: `uv run pytest`, then make a base of a repo with text files, run `git status` in it, and copy it with `--base`. |

## Must never break

- A base still refuses every change the sealed-base criteria of 2026-11-09-m-scratch-tickets list; the line-ending keys are written before the seal, so the seal covers them.
- A copy never reaches back into the target; nothing but the two keys is added to the clone's config.
- `scratch.py` never deletes or changes anything outside the run and never follows a link or junction (lean scratch's link criterion); clearing read-only changes only entries it is removing and their parent folders inside the run.
- A clean never ends in a traceback; an entry it can't remove is reported and the marker stays.

## Failure modes

- Untrusted content in the run (a hunter's repro) swaps a folder for a link while clean runs → the `lstat` and junction checks before each chmod (AC-003); the window between check and chmod is the known limit of Windows' path-based removal (lean scratch's link criterion, narrowed there).
- A caller config with an invalid `core.autocrlf` value → git refuses the clone itself, before this step; a read that fails writes nothing.
- A base made before this change → its seal still matches it (nothing about it changes); only new bases get the keys.

## Out of scope

- The other Windows-only baseline rows (the Windows test-suite item in `docs/sdlc/todo.md`).
- The cost of the tree walk per copy (ticket R6-6/R7-7 of 2026-11-09-m-scratch-tickets).

## Review

- **Recommended and chosen:** security and code, because the risk is high (untrusted run content reaching chmod and delete; the sealed clone's config); chosen by the owner.
- **Verdicts:** `.sdlc/.work/findings/2026-11-12-m-windows-seal-and-clean/` (git-ignored)
  - Round 1: security-r1 PASS (S-1, S-2 unconfirmed medium, S-3 low; the reviewer couldn't run commands, as a hook rewrote its shell calls and auto mode refused them, so it reviewed by reading); code-reviewer-r1 FAIL (C1-1, C1-3, C1-4 high; C1-5, C1-7 medium; C1-6 low bug; C1-8, C1-2 low). The code review is the built-in `code-review high --max-findings all`, rated by me.
  - Round 2: code-reviewer-r2 PASS (C2-3, C2-4, C2-7 medium bugs, fixed after it and closed by verify; C2-1, C2-2, C2-5, C2-6, C2-8, C2-9 low).
- **Fixed:**
  - C1-1 (high): `core.autocrlf` read as raw text missed what git reads as true (a bare key, `2`). Values are typed as git types them and passed to `git clone --config`, so checkout and config agree by construction (`test_a_base_records_the_line_ending_settings_it_was_checked_out_with`: true, bare, `2`, `input`, `eol` with `* text=auto`, and none).
  - C1-3 / S-2 (high, held before this change): a caller's `GIT_DIR`, `GIT_WORK_TREE` or `GIT_INDEX_FILE` (a hook or alias) sent the clone into another repo (confirmed: "working tree … already exists"). `_git` drops the variables `git rev-parse --local-env-vars` lists on every call (`test_a_copy_ignores_the_callers_git_repo_variables`).
  - C1-4, C1-5 / S-1 (high): the parent-folder clear changed a folder by a path an ancestor swap could redirect, for a POSIX rule Windows doesn't have. Gone; `_clear_read_only` changes only the entry, with `follow_symlinks=False` where supported, and skips links and junctions (name-surrogate reparse points), so a link swapped in after the check is not followed (AC-003's swap case).
  - C2-3: dedup and cloud placeholder files (reparse points that aren't name surrogates) are cleared, not skipped (`test_windows_clear_read_only_skips_only_links_among_reparse_points`). C2-4: one chmod path, tested on every OS; the AC-002 and AC-003 tests apply Windows' write-bit rule to `unlink` and `rmdir`. C2-7: the swap case covers the file branch. C1-6: stale `_seal_git` comment. C1-7: the `eol` case could not fail.
  - Seen failing first: AC-001 to AC-003 at Base (`verify.py red --at 202a2b6`); the first link-following build changed the outside folder to 0700, caught by AC-003.
- **Tickets:** C1-2/C2-2 (other checkout settings, `filter.lfs`, `core.longpaths`, still differ from the pinned seal; fails closed); C2-5 (`scope.py`, `secrets_scan.py`, `oracle.py`, `browser.py`, `drafts.py` still inherit `GIT_DIR`; a shared clean-env helper); C2-6 (`includeIf` in the caller's config can give a different line ending than the checkout; fails closed; fix by `clone --no-checkout`, read in the clone, then check out); C2-9 (three git processes per base, one would do); C2-1 (a folder higher up swapped for a junction mid-clean: the recorded known limit of Windows' path-based removal).
- **Drift and manual checks:**
  - Deviations in the state file: task 3 deferred to Windows; the round 1 and round 2 fixes; test changes.
  - **AC-004 (manual, Windows): not yet run.** On Windows: `uv run pytest` (expect `test_clean_reports_size_and_removes_read_only_trees` to pass, then remove its row from `.sdlc/baseline.md` and tick the todo), then make a base of a repo with text files, run `git status` in it, and copy it with `--base`.
- **Security:** the two reviews above; no dependency added (standard library only), so no dependency audit ran.
- **Lessons filed:** one line in `docs/sdlc/recurring-defects.md`; `knowledge/gotchas/copying-a-target-repo.md` (line endings and the caller's git variables).
