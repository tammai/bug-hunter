# Isolation drops every inherited git override but an allowlist, plus the small isolate.py follow-ups

## Why

**Request (verbatim):** "C1 from docs/sdlc/plan-week-2026-11-23.md: isolate.py GIT_* allowlist and follow-ups. Clear the todo items "isolate.py passes every other inherited GIT_* override through" (security review S1 of 2026-11-22-s-git-config-env; structural fix: unset every inherited GIT_* except an allowlist GIT_CONFIG_GLOBAL, GIT_CONFIG_NOSYSTEM, GIT_TERMINAL_PROMPT, GIT_SSL_CAINFO) and "Small isolate.py follow-ups" (8.3 short names via GetLongPathNameW, quoted value with a space inside quotes, one-line error for unpaired UTF-16 surrogate in a Windows env value and fix that test's skip reason, drop extra lstat calls in path fallback, narrow the test guard's PATH filter on macOS)."

`scripts/isolate.py` is the safety boundary for every agent bash call in `/hunt` and `/audit`. 2026-11-22-s-git-config-env dropped `GIT_CONFIG_*`, and its security review (S1) found that git's other environment overrides still pass through. `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `SSH_ASKPASS` and `GIT_PROXY_COMMAND` run an owner's program with the owner's keys. `GIT_CONFIG` and `GIT_CONFIG_SYSTEM` bring back a config file. `GIT_EXEC_PATH`, `GIT_TEMPLATE_DIR`, `GIT_EXTERNAL_DIFF` and `GIT_PAGER`/`GIT_EDITOR` run programs the owner chose. `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` make git act on another repo, and a `GIT_DIR` at the target lets a hunter edit it (constitution III). Today these are caught only when they point into the real home.

The rest are the small review tickets left over from 2026-11-06-m-windows-isolation (CR5, CR10, R3-1, R3-2, the S4 remainder). They all touch the same file and its tests, and the plan for the week groups them as C1.

**The user's words:** None asked. The plan's C1 row recommends the structural fix (an allowlist).

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Unset every inherited variable whose name starts with `GIT_` (folded on Windows, so any spelling) unless isolation exports it. What survives is `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM` and `GIT_TERMINAL_PROMPT` (isolation's own values) and `GIT_SSL_CAINFO` (the owner's value, already in `KEEP_IF_SET`). This replaces the `GIT_CONFIG_VARS` pattern. | Adding the listed names one by one | Git's set of variables is open-ended (`GIT_TRACE*`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, …), and the review asked for an allowlist. |
| Add `SSH_ASKPASS` to `ALWAYS_UNSET` | Leave it | It isn't `GIT_*`, but git calls it for passwords, and the ticket names it. |
| 8.3 short names (Windows): expand each value entry and each root with `GetLongPathNameW` (ctypes, stdlib) before comparing; on failure (a path that doesn't exist) keep the entry as written. | Matching `~1` patterns by text | Only the OS knows which short name maps to which folder. |
| Quoted values: strip whitespace, then quotes, then whitespace again, so `" C:\Users\X\a "` matches. The original R3-2 report isn't kept (`.sdlc/.work` was cleared), so this reading of "a space inside the quotes" is mine. | — | `_win_path` already strips outer whitespace and quotes; only whitespace inside the quotes was missed. |
| Unpaired surrogate: before printing, check that the output encodes for stdout; if not, print one `error:` line naming the variable (never its value) and exit 1. | Catching `UnicodeEncodeError` around `print` | The output is one line built in one place. Checking it first names the culprit and writes nothing to stdout, so `eval` gets nothing. |
| Path fallback: one `os.lstat` per level. Its mode and `st_file_attributes` already show a symlink, a junction (always a reparse point) or a non-folder, so drop `Path.is_junction()` and `Path.is_dir()`. | — | CR10. Each extra call is also another gap where a link could be swapped in. |
| Test guard (`tests/conftest.py`): on POSIX, replace each PATH folder that holds `gh` with a session folder of symlinks to every entry except `gh`. Windows keeps today's filter, since symlinks there need privilege. | Dropping whole folders (today), which hides Homebrew's other tools on macOS; a failing stub `gh` first on PATH | A stub makes `gh` look installed, which changes what the scripts under test do. |

| (Review round 1, CR1/CR2/S2) Isolation exports its own `GIT_EDITOR=true` and `GIT_PAGER=cat` | Dropping them and letting git fall back to its defaults; unsetting `VISUAL`, `EDITOR` and `PAGER` | Without a `GIT_EDITOR`, git falls back to the owner's `VISUAL`/`EDITOR`/`PAGER`, then `vi`, which hangs a call with no terminal. Claude Code used to pass `GIT_EDITOR=true` through. Setting git's own variables leaves other tools' editor alone. |

**Proposals not asked for:** keep `GIT_SSL_CAPATH` too, as the folder form of a corporate CA (`GIT_SSL_CAINFO`'s sibling). Dropped unless you keep it.

## Acceptance criteria

- **AC-001** Given the owner's shell sets `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `SSH_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_EXEC_PATH`, `GIT_TEMPLATE_DIR`, `GIT_EXTERNAL_DIFF`, `GIT_PAGER`, `GIT_EDITOR`, `GIT_CONFIG`, `GIT_CONFIG_SYSTEM`, `GIT_TRACE` and `GIT_ALTERNATE_OBJECT_DIRECTORIES` to values outside the home, when an agent's shell is isolated, then none of them is set there.
- **AC-002** Given the owner's shell sets `GIT_SSL_CAINFO` and its own `GIT_CONFIG_GLOBAL`, when isolated, then `GIT_SSL_CAINFO` keeps the owner's value and `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM` and `GIT_TERMINAL_PROMPT` hold isolation's values.
- **AC-003** Given the owner's shell sets `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` to a repo outside the home (the target), when an isolated shell runs `git` in its own copy, then git acts on the copy and the target's index and refs are unchanged.
- **AC-004** On Windows, a variable whose value names the real home by its 8.3 short name (`C:\Users\TAMMAI~1\x`) is dropped like one that names it in full.
- **AC-005** On Windows, a variable whose value is a quoted path with whitespace inside the quotes (`" C:\Users\X\tools "`) is dropped when the path is in the home.
- **AC-006** Given a Windows environment value with an unpaired UTF-16 surrogate, isolation exits 1 with one `error:` line that names the variable and not its value, prints nothing on stdout, and shows no traceback.
- **AC-007** The path fallback checks each folder level with exactly one `lstat` and no other `stat` call, and still refuses a planted symlink or junction.
- **AC-008** In the test suite on POSIX, a tool that shares a PATH folder with a real `gh` (Homebrew's `/opt/homebrew/bin`) is still found, and `gh` is not.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_isolate.py › test_every_inherited_git_override_is_dropped | `uv run pytest tests/test_isolate.py -k test_every_inherited_git_override_is_dropped` |
| AC-002 | tests/test_isolate.py › test_every_inherited_git_override_is_dropped | `uv run pytest tests/test_isolate.py -k test_every_inherited_git_override_is_dropped` |
| AC-003 | tests/test_isolate.py › test_an_inherited_git_dir_cant_send_git_to_the_target | `uv run pytest tests/test_isolate.py -k test_an_inherited_git_dir_cant_send_git_to_the_target` |
| AC-004 | tests/test_isolate.py › test_points_into_expands_windows_short_names | `uv run pytest tests/test_isolate.py -k test_points_into_expands_windows_short_names` |
| AC-005 | tests/test_isolate.py › test_points_into_matches_whitespace_inside_quotes | `uv run pytest tests/test_isolate.py -k test_points_into_matches_whitespace_inside_quotes` |
| AC-006 | tests/test_isolate.py › test_an_unencodable_environment_value_gives_a_one_line_error | `uv run pytest tests/test_isolate.py -k test_an_unencodable_environment_value_gives_a_one_line_error` |
| AC-007 | tests/test_isolate.py › test_the_path_fallback_checks_each_level_with_one_lstat | `uv run pytest tests/test_isolate.py -k test_the_path_fallback_checks_each_level_with_one_lstat` |
| AC-008 | tests/test_post.py › test_the_gh_guard_keeps_other_tools_in_gh_folders | `uv run pytest tests/test_post.py -k test_the_gh_guard_keeps_other_tools_in_gh_folders` |

AC-004 and AC-005 run on every platform with `WINDOWS` patched and `GetLongPathNameW` stubbed. AC-004 also gets a Windows-only test against a real short name, which skips where the volume has 8.3 names off. The Windows-only part runs in a short Windows session at the end, as in 2026-11-12-m-windows-seal-and-clean.

## Must never break

- Git still has no global or system config in the isolated shell (`test_git_sees_no_global_or_system_config`), and `GIT_CONFIG_*` from the environment is still dropped (`test_git_config_from_the_environment_is_dropped`).
- Toolchain locators and CA bundles the owner set still come through (`test_existing_toolchain_homes_are_kept`, `test_more_ca_variables_are_kept`).
- On POSIX, undecodable environment bytes still pass through unchanged (`test_undecodable_environment_bytes_dont_break_isolation`).
- The path fallback still refuses planted links and junctions (`test_the_path_fallback_refuses_planted_links`).
- No test can reach a logged-in real `gh` (`test_tests_can_never_reach_a_logged_in_real_gh`).
- Isolation fails closed: any error prints nothing on stdout, so `eval "$ISO" || exit 1` stops the call.

## Failure modes

- Untrusted input (the environment, any name case or encoding on Windows) → AC-001 (folded names), AC-006.
- A Windows path form that matching misses (short names, quotes) → AC-004, AC-005.
- Another reader of what changes: the gotcha doc `knowledge/gotchas/isolating-agents-without-a-sandbox.md` describes the fallback's `Path.is_junction` check and the git variables; it is updated in this change.
- Concurrency, persisted data, deploy and rollback: none apply (a stateless script that prints shell code).

## Out of scope

- The other baselined Windows test failures and a Windows CI runner (C5).
- Exporting a `GIT_EDITOR` or `GIT_PAGER` of isolation's own. An inherited one is dropped, and git falls back to its defaults, as it already does on a machine where neither is set.
- `GIT_SSL_CAPATH`, unless you keep the proposal above.

## Review

- **Recommended and chosen:** security and code, because `Risk: high` fires both; chosen by the owner.
- **Verdicts:**
  - Security, round 1: `.sdlc/.work/findings/2026-11-22-m-git-env-allowlist/security-r1.md` → PASS (S1–S3, all low).
  - Code (built-in `code-review high`), round 1: `code-reviewer-r1.md` → FAIL — CR1, CR2, CR3, CR6.
  - Code, round 2: `code-reviewer-r2.md` → PASS, with no high findings. Its medium and low bugs were fixed and closed by `verify.py`.
  - Ratings, round 1: CR1 medium bug (dropping Claude Code's `GIT_EDITOR=true` lets git start `vi` and hang an agent's call); CR2 medium bug (git falls back to the owner's `VISUAL`/`EDITOR`/`PAGER`); CR3 medium bug (a top-level `import ctypes` breaks isolation on a POSIX Python without `_ctypes`); CR4 low ticket (`GIT_SSL_CAPATH`, declined at Define); CR5 low ticket (pre-existing ssh identity); CR6 low bug (the error named a derived variable).
  - Ratings, round 2: R2-1 medium bug (the no-ctypes test on Windows); R2-2 low ticket (`GIT_SSL_CAPATH`, `GIT_PROXY_SSL_CAINFO`); R2-3 medium bug (the error could name an unset secret); R2-4 low bug (`\??\` paths and mapped network drives reached `GetLongPathNameW`); R2-5 low bug (relative PATH entries in the gh guard); R2-6 low (see Drift); R2-7 low ticket (pre-existing).
- **Fixed:**
  - CR1, CR2 and S2: isolation exports `GIT_EDITOR=true` and `GIT_PAGER=cat` (`test_git_runs_no_editor_or_pager_the_owner_chose`; AC-001's test pins both values).
  - CR3: `ctypes` is imported inside `_long_name`, on Windows only (`test_isolation_runs_on_a_python_without_ctypes`).
  - CR6 and R2-3: `_unwritable` names the export that can't be written, or the owner's variables it was built from (`test_the_encoding_error_names_the_inherited_variable`).
  - S1 and R2-4: `_long_name` asks only about drive-letter paths and skips network drives. The fake-`kernel32` test also covers the longest-prefix walk that darwin couldn't run (`test_long_name_expands_the_longest_existing_prefix_and_skips_unc`).
  - S3 and R2-5: the gh invariant asserts no `gh` on PATH on POSIX, and `gh_free_path` checks its shim and links from absolute folders.
  - R2-1: the no-ctypes test skips on Windows.
- **Tickets:** R2-2/CR4 (`GIT_SSL_CAPATH`, `GIT_PROXY_SSL_CAINFO`), CR5 (ssh identity), R2-7 (`_refuse_links` checks by path), and names that aren't shell identifiers. All are in `docs/sdlc/todo.md`.
- **Drift and manual checks:**
  - Six Deviations lines: AC-002 shares AC-001's test, and five test changes. Each change is stricter, and each was re-shown red at base 35c520c.
  - Superseded: the round-1 Decisions row (accepted by the owner at the trust-anchor check) replaces the Out of scope line on `GIT_EDITOR`/`GIT_PAGER`.
  - Still to do: AC-004's real short-name test, AC-007's junction path and a real `nt.environ` surrogate run only on Windows. They are for the planned Windows session.
- **Security:** no high or critical findings, and no secrets in the diff. There is no dependency audit: the project has no runtime dependencies, the change adds none, and `pip-audit` isn't installed, so it couldn't run (not counted as a pass).
- **Lessons filed:** [knowledge/gotchas/isolating-agents-without-a-sandbox.md](../../../knowledge/gotchas/isolating-agents-without-a-sandbox.md), covering git's environment, the editor and pager, ssh, short names and surrogates.
