# Isolation and the hunt path on Windows

## Why

**Request (verbatim):** "isolate.py fails on Windows and does not isolate there. Every hunter, auditor and verifier runs it first, so /hunt and /audit can't run on Windows at all.
(a) Crash: `_open_folder` uses os.O_DIRECTORY, os.O_NOFOLLOW and dir_fd. Windows Python has none of them (os.supports_dir_fd is empty). `python3 -I scripts/isolate.py <scratch>` raises AttributeError: module 'os' has no attribute 'O_DIRECTORY' (line 137). `_write` and `_refuse_links` have the same problem.
(b) No isolation even without the crash: Windows tools find config and credentials through USERPROFILE (git, npm, ssh), APPDATA (gh, npm) and LOCALAPPDATA (caches, tool installs). The plan never redirects these. `_points_into` splits on os.pathsep but compares with '/' separators, so it never matches `C:\Users\<name>\...` values, and variables pointing into the real profile are not unset.
Fix: keep the POSIX descriptor-relative path unchanged where it is supported. Where it is not, use a path-based fallback that refuses symlinks and junctions at every level (lstat, Path.is_junction). Redirect USERPROFILE, APPDATA and LOCALAPPDATA (plus HOMEDRIVE and HOMEPATH) into the scratch home. Make `_points_into` compare normalized, case-insensitive Windows paths. If isolation can't be set up, exit non-zero with a clear message, never half-isolated. Output stays the shell code that Git Bash evals."

Every hunter, auditor and verifier starts each Bash call with `isolate.py`, so on Windows `/hunt` and `/audit` can't run at all today. Once it runs, it must really keep the agent's tools off the owner's profile, logins and secrets, as it does on Linux and macOS.

**The user's words (the owner, through the coordinator):**
- On the 24 pre-existing Windows failures outside `isolate.py`: "option A widened to the hunt path. Fix isolate.py, and also fix any of the 24 other failures that /hunt or /audit need in order to actually run on Windows … Judge by whether the command path breaks, not by test noise. Record the remaining failures (for example test-only fake-gh shebangs and post.py) in .sdlc/baseline.md as known pre-existing, with a todo for a separate Windows test-suite change. Proof at the end: step 4 of the brief, plus a dry run of /hunt's scripted steps on Windows (scope.py, drafts.py dir, known.py, throwaway.py into a mktemp -d, isolate.py) completing without error."
- After the test suite filed real issues (below): "add the test-safety fix to this change FIRST, before any further full test run. Give the fake gh a wrapper Windows can run (gh.cmd). Run the post tests, and any test that shells out to gh, with the real gh removed from PATH and GH_TOKEN/GITHUB_TOKEN unset, so a missing fake fails loudly instead of reaching the real gh."

**Incident that shaped this change.** Measuring the Windows baseline ran `uv run pytest` three times, and that filed six real issues (#12–#17) on tammai/bug-hunter from the owner's `gh` login. The coordinator has since deleted them. Cause: `tests/conftest.py`'s fake `gh` is a `#!python` script, which Windows can't run, so `post.py` found the real `gh.exe` on PATH. In `test_shows_url_when_recording_fails_after_filing` it then resolved the repo from the worktree's `origin`. The guard below went in first, as the owner asked. It was proven with a run of `tests/test_post.py` alone with every proxy pointed at a dead port, and the issue list was the same before and after.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Choose the fallback by capability: descriptor-relative only when `os.open`, `os.mkdir`, `os.replace` and `os.unlink` take `dir_fd` and `O_DIRECTORY` and `O_NOFOLLOW` exist (`DIR_FD`) | Branching on `os.name` | The POSIX path stays byte-for-byte the same wherever it works, and a test can force the fallback on Linux CI, so its link refusal is tested there too |
| The fallback creates each level with `mkdir`, then `lstat`s it and refuses a symlink, a junction (`Path.is_junction`) or any other reparse point (`FILE_ATTRIBUTE_REPARSE_POINT`), or anything that isn't a folder. Files are written to a temp name with `O_CREAT \| O_EXCL`, then `os.replace`d, which replaces a planted link rather than following it. The top of the scratch home, `.config` and (Windows) the AppData folders are scanned for links, as on POSIX | Opening handles with `CreateFileW(FILE_FLAG_OPEN_REPARSE_POINT)` through ctypes | That closes the check-then-use gap, but it's a lot of Win32 code in a stdlib script. The gap needs code already running in the scratch while `isolate.py` runs, which is the same "not a sandbox" limit the gotcha records |
| On Windows, export USERPROFILE, APPDATA (`home\AppData\Roaming`), LOCALAPPDATA (`home\AppData\Local`), HOMEDRIVE and HOMEPATH (from the scratch home), and **TEMP and TMP** (`home\AppData\Local\Temp`), and create those folders | Leaving TEMP and TMP alone | They point into the real LOCALAPPDATA, so the into-the-profile rule would unset them, and many Windows tools fail without them. Redirecting them keeps temp files in the scratch dir. **The owner approved this (2026-11-06).** |
| On Windows the plan works from `nt.environ`, which keeps the original letter case, and compares names case-insensitively. Any other spelling of an exported name is unset first. `PATH` is matched in any case | `dict(os.environ)` as on POSIX | Windows Python uppercases every key in `os.environ`, but Git Bash keeps the case. So `unset ONEDRIVE` would leave `OneDrive`, and `unset MYAPI_TOKEN` would leave `MyApi_Token` for every native child (checked on this machine) |
| The real profile is every one of HOME, USERPROFILE, APPDATA and LOCALAPPDATA that is set. `_points_into` on Windows compares `ntpath.normcase(ntpath.normpath(…))` forms, so it is case-insensitive, takes either separator, splits on `;`, and treats a drive root (`C:\`, `\`, `//`) as matching nothing | Only HOME | Roaming profiles and redirected folders put APPDATA and LOCALAPPDATA outside USERPROFILE, and HOME in Git Bash can differ from USERPROFILE |
| The hunt and audit scripts (`scope`, `drafts`, `known`, `findings`, `throwaway`, `secrets_scan`, `isolate`) switch stdout and stderr to UTF-8 at start-up, and `throwaway.py` decodes `git rev-parse` as UTF-8 | `python3 -X utf8` in every command and agent line | Windows Python before 3.15 writes in the ANSI code page (cp1252 here). `naïve.py` comes out as byte 0xEF, which the reader decodes wrongly, and a name outside cp1252 (`tệp.py`) crashes the print. `throwaway.py` misread the repo path `my repö`: the clone failed, and a destination inside the repo wasn't refused. This machine's `python3` is 3.15 (UTF-8 by default), which is why a plain dry run passed. Under uv's 3.13 it breaks. Changing every prompt line would also change the agents' fixed isolation line |
| Test guard: a session-wide autouse fixture in `tests/conftest.py` unsets the gh token variables, points `GH_CONFIG_DIR` at an empty folder (a reached gh is logged out) and drops PATH folders holding a `gh`. It keeps a folder that also holds `git` (`/usr/bin` on CI), where the empty config is the guard | A `gh.cmd` wrapper, as the owner suggested | On Windows `subprocess.run(["gh", …])` only finds `.exe` files (checked: a `.cmd` on PATH gives WinError 2), so a `gh.cmd` would never run. Making it run means `post.py` and `known.py` resolving `gh` through `shutil.which`, and a `.cmd` run that way passes draft titles through `cmd.exe`, an injection risk. **The owner chose this (2026-11-06):** the fake-gh tests stay in the baseline, failing safely (see Out of scope) |
| Tests call Git Bash by its path from `git --exec-path` on Windows and read the environment with bash builtins (`compgen -e`), not `env` | `bash` from PATH | Windows searches System32 before PATH, so `bash` is WSL's `bash.exe`. Started from PowerShell, PATH has no Git `usr\bin`, so `env` isn't found |

**Bug:** `python3 -I scripts/isolate.py "$(mktemp -d)"` in Git Bash on Windows 11 with Python 3.15 prints `AttributeError: module 'os' has no attribute 'O_DIRECTORY'` (`_open_folder`, line 137). Root cause: the script assumes POSIX descriptor-relative calls, and `_plan` assumes POSIX paths and case-sensitive variable names. Proof: 23 `tests/test_isolate.py` failures before this change (`.sdlc/.work/baseline-windows.txt`).

**Proposals not asked for:** a Windows runner in CI (`windows-latest`), so the Windows-only tests run on every PR. It would fail on the baseline tests until the Windows test-suite change, so it's a ticket, not part of this change.

## Acceptance criteria

- **AC-001** Given a Python without descriptor-relative calls (Windows, or `DIR_FD` forced off), when isolation runs, then it exits 0, creates `home`, `home/.config` and `no-gh` (and on Windows the AppData and Temp folders), and writes the carried version files and `gradle.properties`.
- **AC-002** Given the path fallback and a planted symlink or junction at any level (the scratch home itself, a folder inside it such as `.gradle`, on Windows `AppData`), when isolation runs, then it exits 1 with an `error:` line naming a link, prints nothing on stdout, shows no traceback and writes nothing through the link.
- **AC-003** Given Windows, when the output is evalled in Git Bash, then USERPROFILE, APPDATA, LOCALAPPDATA, TEMP and TMP point into the scratch home, and HOMEDRIVE followed by HOMEPATH spells the scratch home.
- **AC-004** Given Windows, when the output is evalled in Git Bash, then inherited variables pointing into the real profile (under HOME, USERPROFILE, APPDATA or LOCALAPPDATA, in any letter case or separator) are gone, secret-named variables in any letter case (`MyApi_Token`) are gone, and PATH is unchanged.
- **AC-005** Given Windows paths, `_points_into` matches `c:/users/x/AppData` against `C:\Users\X`, matches inside a `;` list, doesn't match `C:\Users\X2`, and treats a drive root as matching nothing.
- **AC-006** Given isolation, when git runs, then `git config --list --show-origin` lists no file at all (no global, system or ProgramData config), so no `credential.helper` is set.
- **AC-007** Given a scratch home that can't be created (a file is in its place), when isolation runs, then it exits 1 with one `error:` line, an empty stdout and no traceback.
- **AC-008** Given a tracked file named `src/tệp.py` (outside the Windows code page), when `scope.py` runs, then its JSON lists that name, encoded as UTF-8.
- **AC-009** Given a repo whose path has non-ASCII (`my repö`), when `throwaway.py` is asked to copy it into a folder inside the repo, then it refuses with "inside" and creates nothing there.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_isolate.py › test_the_path_fallback_creates_the_home_folders | `uv run pytest tests/test_isolate.py::test_the_path_fallback_creates_the_home_folders` |
| AC-002 | tests/test_isolate.py › test_the_path_fallback_refuses_planted_links | `uv run pytest tests/test_isolate.py::test_the_path_fallback_refuses_planted_links` |
| AC-003 | tests/test_isolate.py › test_windows_profile_variables_move_into_the_scratch_home | `uv run pytest tests/test_isolate.py::test_windows_profile_variables_move_into_the_scratch_home` |
| AC-004 | tests/test_isolate.py › test_windows_profile_paths_and_any_case_secrets_are_dropped | `uv run pytest tests/test_isolate.py::test_windows_profile_paths_and_any_case_secrets_are_dropped` |
| AC-005 | tests/test_isolate.py › test_points_into_compares_windows_paths | `uv run pytest tests/test_isolate.py::test_points_into_compares_windows_paths` |
| AC-006 | tests/test_isolate.py › test_git_sees_no_global_or_system_config | `uv run pytest tests/test_isolate.py::test_git_sees_no_global_or_system_config` |
| AC-007 | tests/test_isolate.py › test_isolation_that_cant_be_set_up_exits_with_a_clear_error | `uv run pytest tests/test_isolate.py::test_isolation_that_cant_be_set_up_exits_with_a_clear_error` |
| AC-008 | tests/test_scope.py › test_names_outside_the_windows_code_page_print_as_utf8 | `uv run pytest tests/test_scope.py::test_names_outside_the_windows_code_page_print_as_utf8` |
| AC-009 | tests/test_throwaway.py › test_refuses_a_dest_inside_the_repo | `uv run pytest tests/test_throwaway.py::test_refuses_a_dest_inside_the_repo` |

AC-003 and AC-004 run only on Windows and skip elsewhere, with a reason. AC-005 forces the Windows comparison, so it runs everywhere.

## Must never break

- On a POSIX Python the descriptor-relative path (`O_NOFOLLOW`, `dir_fd`, rename inside the folder) runs unchanged, and every existing POSIX test passes on Linux CI.
- `isolate.py` prints shell code on stdout only when isolation is complete. Every failure exits non-zero with nothing on stdout, so the agents' `ISO="$(…)" && eval "$ISO" || exit 1` stops the call.
- No test run can reach a logged-in real `gh` (`tests/test_post.py::test_tests_can_never_reach_a_logged_in_real_gh`; before the guard existed it failed with `KeyError: 'GH_CONFIG_DIR'`).
- No secret value appears in any output, test log or this record.

## Failure modes

- Untrusted input: code from an earlier agent call plants a link in the scratch → AC-002.
- Partial failure: a folder or file can't be created → AC-007; output is all or nothing.
- A race: a link swapped in between the fallback's check and its write. Accepted by the owner (2026-11-06) and documented (Decisions, row 2).
- Concurrency, scale, persisted data: none apply.

## Out of scope

- **The remaining pre-existing Windows test failures,** listed in `.sdlc/baseline.md` with their causes, with a todo for a separate Windows test-suite change. None of them is on the `/hunt` or `/audit` command path:
  - the fake-gh shebang (`test_known` ×2, `test_post` ×4);
  - `HOME` vs `USERPROFILE` in tests (`test_drafts::test_dir_is_outside_target_named_after_origin`, `test_findings::test_audit_folder_and_numbering`);
  - POSIX file modes (`test_findings` ×3);
  - read-only git objects on cleanup (`test_drafts::test_dir_names_never_collide_or_escape`);
  - CRLF written in text mode by the fixture (`test_secrets_scan`);
  - names Windows forbids (`test_stacks`);
  - non-UTF-8 file names (`test_scope::test_skips_names_that_are_not_utf8`);
  - symlink privilege (`test_throwaway::test_refuses_symlinks_out_of_the_copy_and_a_used_dest`).
- **Making the fake gh run on Windows** (needs a `shutil.which` change to `post.py` and `known.py`; see Decisions).
- **What environment variables can't redirect on Windows:**
  - Windows OpenSSH's agent named pipe;
  - Windows Credential Manager;
  - DPAPI;
  - programs that find their folders through the Known Folders API instead of APPDATA (.NET and NuGet, PowerShell).

  These go in the README and the gotcha.
- **Scratch paths with whitespace** (a Windows user name with a space) stay refused, as before.
- **A Windows CI runner** (ticket, above).

## Real check on this machine (Windows 11, Git Bash, 2026-11-06, after review round 1)

**The brief's step 4:** `ISO="$(python3 -I scripts/isolate.py "$(mktemp -d)")" && eval "$ISO"`, then the variables, git's view of its config, and gh. The script is `.sdlc/.work/step4.sh`. It prints names, counts and comparisons, never the value of a real secret.
- Before isolation, `git config --global --list` showed 9 lines of the owner's settings. After it, none.
- The only config files git lists are the current repo's own `.git/config`, because the check ran inside the repo.
- The two secret-named variables left are the `GH_TOKEN` and `GH_ENTERPRISE_TOKEN` placeholders.

```text
python3: Python 3.15.0
before: HOME=/c/Users/Admin USERPROFILE=C:\Users\Admin
before: git global settings: 9 lines
scratch: /c/Users/Admin/AppData/Local/Temp/tmp.FOx6AH15lJ (C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ)
HOME=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home
USERPROFILE=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home
APPDATA=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home\AppData\Roaming
LOCALAPPDATA=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home\AppData\Local
HOMEDRIVE=C:
HOMEPATH=\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home
TEMP=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home\AppData\Local\Temp
TMP=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home\AppData\Local\Temp
XDG_CONFIG_HOME=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home\.config
GH_CONFIG_DIR=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\no-gh
GIT_CONFIG_GLOBAL=/dev/null
GIT_CONFIG_NOSYSTEM=1
--- git config --global --list:
(exit 0)
--- git config --list --show-origin (files only):
file:C:/Users/Admin/orca/bug-hunter/.git/config	core.repositoryformatversion=0
file:C:/Users/Admin/orca/bug-hunter/.git/config	core.filemode=false
file:C:/Users/Admin/orca/bug-hunter/.git/config	core.bare=false
file:C:/Users/Admin/orca/bug-hunter/.git/config	core.logallrefupdates=true
file:C:/Users/Admin/orca/bug-hunter/.git/config	core.symlinks=false
file:C:/Users/Admin/orca/bug-hunter/.git/config	core.ignorecase=true
file:C:/Users/Admin/orca/bug-hunter/.git/config	remote.origin.url=https://github.com/tammai/bug-hunter
file:C:/Users/Admin/orca/bug-hunter/.git/config	remote.origin.fetch=+refs/heads/*:refs/remotes/origin/*
file:C:/Users/Admin/orca/bug-hunter/.git/config	branch.main.remote=origin
file:C:/Users/Admin/orca/bug-hunter/.git/config	branch.main.merge=refs/heads/main
file:C:/Users/Admin/orca/bug-hunter/.git/config	push.autosetupremote=true
file:C:/Users/Admin/orca/bug-hunter/.git/config	branch.tammai/bh-windows-isolation.base=refs/remotes/origin/main
(file entries: 12)
--- git config --show-origin --get-all credential.helper:
(exit 1)
--- secret-named variables left: 2
--- gh auth token is the placeholder, not a stored login: yes
GH_TOKEN=isolated-no-token
GH_ENTERPRISE_TOKEN=isolated-no-token
TMPDIR=C:\Users\Admin\AppData\Local\Temp\tmp.FOx6AH15lJ\home\AppData\Local\Temp
```

**Dry run of `/hunt` and `/audit`'s scripted steps** (`.sdlc/.work/dryrun.sh`) on this repo, with 13 tracked files edited and 4 untracked:
- It ran under Python 3.15 and under uv's 3.13. Under 3.13 the scripts printed in cp1252 before this change.
- The last line is the agents' own order: isolation, then the throwaway copy, in the same call.
- The copy has the 13 tracked edits. Untracked files are left out on purpose.
- `known.py` only reads the open issues.

```text
== Python 3.15.0  repo has 17 uncommitted paths
ok   scope.py: {
   "parts": [
     {
       "id": 1,
       "dir": ".sdlc/ci",
       "files": [
       
ok   scope.py --focus security: {
   "parts": [
     {
       "id": 1,
       "dir": ".",
       "files": [
         "pypr
ok   drafts.py dir: C:\Users\Admin\.bug-hunter\github.com\tammai\bug-hunter\drafts
ok   known.py: ## Open issues
 - none
 
 ## Earlier findings
 - none
ok   findings.py dir: C:\Users\Admin\.bug-hunter\github.com\tammai\bug-hunter\audit
ok   known.py --audit: ## Earlier audit findings
 - none
ok   secrets_scan.py: [
   {
     "path": ".sdlc/state/2026-11-06-l-security-pii-audit.md",
     "line": 80,
   
ok   throwaway.py: C:\Users\Admin\AppData\Local\Temp\tmp.2kqZIFsH0y\copy-a
ok   isolate.py + throwaway.py (agent line): copy has 13 uncommitted paths, like the repo
== Python 3.13.13  repo has 17 uncommitted paths
ok   scope.py: {
   "parts": [
     {
       "id": 1,
       "dir": ".sdlc/ci",
       "files": [
       
ok   scope.py --focus security: {
   "parts": [
     {
       "id": 1,
       "dir": ".",
       "files": [
         "pypr
ok   drafts.py dir: C:\Users\Admin\.bug-hunter\github.com\tammai\bug-hunter\drafts
ok   known.py: ## Open issues
 - none
 
 ## Earlier findings
 - none
ok   findings.py dir: C:\Users\Admin\.bug-hunter\github.com\tammai\bug-hunter\audit
ok   known.py --audit: ## Earlier audit findings
 - none
ok   secrets_scan.py: [
   {
     "path": ".sdlc/state/2026-11-06-l-security-pii-audit.md",
     "line": 80,
   
ok   throwaway.py: C:\Users\Admin\AppData\Local\Temp\tmp.IV1OLwGD73\copy-a
ok   isolate.py + throwaway.py (agent line): copy has 13 uncommitted paths, like the repo
```

## Review

- **Recommended and chosen:** security (Risk high) and code at high depth (Risk high, and Public Surface isn't `- none`). This is a high-risk M, so the user would normally choose. I took the recommendation, as a dispatched worker running unattended, and logged it in the state file.
- **Verdicts:**
  - Security, `.sdlc/.work/findings/2026-11-06-m-windows-isolation/security-r1.md`: FAIL — S1, S2, S3.
  - Code, `code-reviewer-r1.md`: FAIL — CR1, CR2, CR3, CR4.
  - Security, `security-r2.md`: PASS.
  - Code, `code-reviewer-r2.md`: FAIL — R2-2, R2-3, R2-7. The owner chose one more fix round.
  - Code, `code-reviewer-r3.md`: PASS.
  - The code review is the built-in `code-review` skill at `high`. Each finding was rated by the change's ACs, its must-never-break lines and the constitution; the reports hold each rating.
- **Fixed:**
  - **S1 / CR1 (high).** `DIR_FD` checked `os.replace`, which CPython never lists in `os.supports_dir_fd` (only `os.rename`). The descriptor-relative path was therefore off on Linux and macOS too, which broke must-never-break line 1. Now `_dir_fd()` checks `os.rename`. Tests: `test_the_descriptor_path_is_used_where_cpython_supports_it`, and `test_the_descriptor_path_is_on_for_this_posix_python` on POSIX. WSL's Python 3.12 reports `DIR_FD True`.
  - **S2 (high).** An empty `GH_CONFIG_DIR` doesn't log gh out on Windows: gh reads the owner's login from Credential Manager. `isolate.py` now exports `GH_TOKEN` and `GH_ENTERPRISE_TOKEN` as a placeholder, which gh prefers. Tests: `test_home_caches_and_credentials_move_into_scratch`, and the real check above. Round 2 confirmed live that `gh api user` is refused.
  - **S3 (high).** The test guard has the same hole. It now sets the four gh token variables to a placeholder. Test: `test_tests_can_never_reach_a_logged_in_real_gh`.
  - **CR2.** `reconfigure` reset the error handler to strict. It now keeps `errors=stream.errors`. Test: `test_undecodable_environment_bytes_dont_break_isolation` (R2-2 made it able to fail).
  - **CR3.** `TMPDIR` is now redirected on Windows.
  - **CR4.** The nvm-windows and pyenv-win locators are kept.
  - **S4 and R2-3.** `_win_path` now handles quoted values, `\\?\`, `//?/` and the UNC long forms, and list entries with leading spaces.
  - **S5.** The Temp folder is now scanned for planted links.
  - **R2-7.** A POSIX-only `DIR_FD` assertion was added.
- **Tickets** (in `docs/sdlc/todo.md` unless noted):
  - **R2-1 (owner kept it as designed).** The `GH_TOKEN` placeholder makes tools that read `GH_TOKEN` get a 401 where an anonymous call would have worked.
  - **R2-4 (owner kept it as designed).** With `NVM_HOME` and `PYENV_HOME` kept, an explicit `nvm install` or `nvm use` changes the owner's real install. That's the same exposure as `NVM_DIR` on POSIX.
  - **CR5 / R2-5.** The test guard's PATH filter drops whole folders, such as Homebrew on macOS. The owner ordered the real gh off PATH.
  - **CR6 / R2-6.** `post.py` doesn't switch its output to UTF-8. This belongs to the Windows test-suite item.
  - **CR8.** On Windows, Git Bash turns a HOME of `/` into its install folder.
  - **CR9 / R2-8.** The copied `reconfigure` lines are kept, because `python3 -I` can't import a shared helper.
  - **CR10 / R2-9.** The fallback makes extra `lstat` calls.
  - **R3-1.** A Windows value with an unpaired surrogate gives a traceback, though it still fails closed. The test's skip reason is inexact.
  - **R3-2.** A quoted value with a space inside the quotes isn't matched.
  - **S4 remainder.** 8.3 short names aren't matched.
  - **Inherited `GIT_CONFIG_*` variables** can inject git config without any file.
- **Drift and manual checks:**
  - Deviation 1: the gh guard was built before Define, on the owner's order, after the suite filed real issues.
  - Deviation 2: `.sdlc/baseline.md` was created with 16 Windows-only failures, with the owner's OK.
  - No `manual` AC.
  - verify reports no drift. Its only failing step is the full suite: 16 failed, 123 passed, 5 skipped. All 16 failures are in the baseline, on Windows and from PowerShell alike.
  - After Review started, the AC tests and this file's real-check section changed (round 1 fixes). The owner accepted that.
  - The AC-003 and AC-004 tests run only on Windows. AC-005 runs everywhere.
- **Security:**
  - No secret values appear in the diff or the reports. Every probe discarded token output.
  - There are no runtime dependencies (`dependencies = []`, stdlib only), so no dependency audit applies.
  - The security hooks raised nothing.
- **Lessons filed:**
  - [knowledge/gotchas/isolating-agents-without-a-sandbox.md](../../../knowledge/gotchas/isolating-agents-without-a-sandbox.md), new Windows section.
  - Four lines in `docs/sdlc/recurring-defects.md`.
- **Process note:** the brief's "never post to GitHub" was broken by the test suite itself. On Windows, the fake gh fell through to the real gh, which filed issues #12–#17; the coordinator deleted them. That is why the guard came first.
