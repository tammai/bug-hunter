# Known failures baseline

<!-- Written by /sdlc:setup (sdlc v3.2.1). Yours from then on: the plugin never overwrites it.
     Review (Stage 3) fails only on failures NOT listed here. Rules:
     - Shrinks on its own: when a listed item passes, the build removes it and says so in the change file's `## Review`.
     - Never grows silently: adding an item needs the user's OK and a Deviations entry in that feature's state.md.
     - Fixing items is its own S-track work, not a side job inside a feature. -->

Recorded: 2026-11-06 at commit bc45a9d, running `uv run pytest` on Windows 11 (Git Bash, uv's Python 3.13); added with the owner's OK in docs/sdlc/changes/2026-11-06-m-windows-isolation.md.

Every row passes on Linux CI and fails only on Windows, because of how the test builds its fixture there. None is on the `/hunt` or `/audit` command path. Fixing them is the Windows test-suite item in `docs/sdlc/todo.md`.

## Failing tests

| Package | Test (file › name) | Failure, one line | Since |
|---|---|---|---|
| (root) | tests/test_known.py › test_lists_open_issues_and_earlier_drafts | Windows only: the fake `gh` is a `#!python` script, which Windows can't run; the guard in `tests/conftest.py` makes it fail with "gh is not installed" instead of reaching the real `gh`. | 2026-11-06 |
| (root) | tests/test_known.py › test_titles_are_cleaned_and_a_full_page_is_flagged | Windows only: fake `gh`, as above. | 2026-11-06 |
| (root) | tests/test_post.py › test_files_named_drafts_once | Windows only: fake `gh`, as above. | 2026-11-06 |
| (root) | tests/test_post.py › test_refuses_before_filing_and_keeps_partial_progress | Windows only: fake `gh`, as above. | 2026-11-06 |
| (root) | tests/test_post.py › test_refuses_odd_numbers_duplicates_and_unusable_record | Windows only: fake `gh` and `chmod(0o555)`, which doesn't make a folder read-only on Windows. | 2026-11-06 |
| (root) | tests/test_post.py › test_shows_url_when_recording_fails_after_filing | Windows only: fake `gh` and `chmod`, as above. | 2026-11-06 |
| (root) | tests/test_drafts.py › test_dir_is_outside_target_named_after_origin | Windows only: the test moves `HOME`, but `Path.home()` reads `USERPROFILE` on Windows. | 2026-11-06 |
| (root) | tests/test_findings.py › test_audit_folder_and_numbering | Windows only: `HOME` vs `USERPROFILE`, as above. | 2026-11-06 |
| (root) | tests/test_drafts.py › test_dir_names_never_collide_or_escape | Windows only: `shutil.rmtree` can't delete git's read-only object files on Windows. | 2026-11-06 |
| (root) | tests/test_scope.py › test_live_keeps_only_parts_serving_http | Windows only: `shutil.rmtree` PermissionError on git's read-only object files, as above; fails on `main` too. Added with the owner's OK in docs/sdlc/changes/2026-11-08-m-b0-live-validation.md. | 2026-11-08 |
| (root) | tests/test_findings.py › test_script_outputs_become_findings | Windows only: asserts POSIX mode `0o600`; Windows reports `0o666`. | 2026-11-06 |
| (root) | tests/test_findings.py › test_report_and_inventory | Windows only: POSIX mode, as above. | 2026-11-06 |
| (root) | tests/test_findings.py › test_known_secrets_are_withheld_and_code_is_not | Windows only: POSIX mode, as above. | 2026-11-06 |
| (root) | tests/test_secrets_scan.py › test_finds_secrets_without_printing_them | Windows only: the fixture writes `\r\n` in text mode, which Windows turns into `\r\r\n`, so the line number moves. | 2026-11-06 |
| (root) | tests/test_stacks.py › test_install_steps_are_exact_and_unsafe_folders_get_none | Windows only: the fixture's folder names have characters Windows forbids (such as `"`). | 2026-11-06 |
| (root) | tests/test_scope.py › test_skips_names_that_are_not_utf8 | Windows only: Windows file names can't hold non-UTF-8 bytes; git's index entry can't be checked out or decoded there. | 2026-11-06 |
| (root) | tests/test_throwaway.py › test_refuses_symlinks_out_of_the_copy_and_a_used_dest | Windows only: creating a symlink on Windows needs Developer Mode or admin (WinError 1314); with Developer Mode on, Git for Windows' `core.symlinks=false` checks the committed link out as a plain file, so the copy has no link to refuse. | 2026-11-06 |
| (root) | tests/test_throwaway.py › test_copy_from_a_base_is_independent_and_checked | Windows only: `core.symlinks=false`, as above, so the base's `src/inside.py` is a plain file and `is_symlink()` fails. Fails on `main` too. Added with the owner's OK in docs/sdlc/changes/2026-11-09-m-scratch-tickets.md. | 2026-11-11 |
| (root) | tests/test_throwaway.py › test_copy_from_a_base_falls_back_when_cp_fails | Windows only: `core.symlinks=false`, as above. Fails on `main` too; added with the owner's OK, as above. | 2026-11-11 |
| (root) | tests/test_scratch.py › test_clean_reports_size_and_removes_read_only_trees | Windows only, a real bug: `scratch.py clean` can't remove a read-only folder (Go's module cache) on Windows, "Access is denied". Fails on `main` too; a todo in docs/sdlc/todo.md. Added with the owner's OK, as above. | 2026-11-11 |

## Lint and type errors

Counts per rule and file. Review fails if any count goes **up**, or a rule/file appears that isn't listed.

| Package | Tool | Rule | File | Count |
|---|---|---|---|---|
| — | none | | | |

## Build warnings / other

- none
