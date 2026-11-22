# The test suite builds its fixtures so Windows can run them, and CI runs it on windows-latest

## Why

**Request (verbatim):** "Make the test suite pass on Windows: the 19 Windows-only failures in `.sdlc/baseline.md` ... then add a `windows-latest` CI runner." The brief adds: a fake `gh` Windows can run without passing titles through cmd.exe, `USERPROFILE` alongside `HOME`, POSIX mode asserts made platform-aware, read-only git objects removed with an error handler, CRLF via binary writes, fixture names Windows forbids, and symlink tests skipped with a stated reason when symlinks can't be created.

Every baseline row is a fixture problem, not a product one. While they stay red nobody runs the suite on Windows, so Windows regressions in `isolate.py`, `throwaway.py` and `scratch.py` go unseen. This change touches tests and CI only; no file under `scripts/` changes.

**Verified only by reasoning until CI runs:** nothing here can run Windows. Every fix keeps macOS green (and Linux, same code paths), and the helpers' POSIX halves are tested here. Each Windows half is argued in Decisions and gets its first real run on the new `windows-latest` job. The baseline rows stay until that run shows them passing.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| The fake `gh` is the Python interpreter under the name `gh`, in a folder laid out as a venv (`pyvenv.cfg` with `home` = the base Python). A `.pth` file in its site-packages imports the fake at startup, which reads `sys.orig_argv`, flushes and `os._exit`s before Python looks for a script. POSIX: `bin/gh` is a symlink to `sys._base_executable`. Windows: `Scripts\gh.exe` is a copy of the base `python.exe` with the DLLs beside it. One mechanism on every OS, so macOS and Linux test the hook. | A `gh.cmd`/`gh.bat` (CreateProcess finds only `.exe`, and a batch file passes titles through cmd.exe); copying the venv's `python.exe` launcher (its target name differs between 3.12 and 3.13); compiling an exe; uv's trampoline format | `subprocess.run(["gh", …])` on Windows finds only `gh.exe`. A real `python.exe` doesn't depend on launcher internals. CPython clears `__PYVENV_LAUNCHER__` at startup (`Modules/getpath.c`), so it can't leak from the script under test and point `gh.exe` at another prefix. |
| The fake only acts when invoked as `gh` (`sys.orig_argv[0]` stem), and the folder on PATH holds only `gh` (and, on Windows, Python's DLLs) | Building it with `venv.EnvBuilder` | EnvBuilder puts `python`/`python3` in the same folder, so a script calling `python3` would hit the fake. |
| A folder "can't be written" on Windows through a deny ACL: `icacls <dir> /deny *S-1-1-0:(WD,AD)` (add file, add subfolder), removed with `/remove:d`. POSIX keeps `chmod 0o555`. Shared as `lock_dir`/`unlock_dir` in `conftest.py`; the fake `gh` runs the same two lines inline (it can't import pytest). | Guarding the two `post.py` blocks by platform (a skipped block isn't a pass); `(W)`, which also denies SYNCHRONIZE and READ_CONTROL and so breaks listing the folder | Deny entries apply to the owner and to elevated admins. Only the two rights that create entries are denied, so reads and listing still work. |
| POSIX mode asserts go through `mode_is(path, mode)`, which is true on Windows | Asserting Windows' `0o666`/`0o777` | Windows has no POSIX bits: `os.chmod` only flips the read-only flag, so there's nothing to check. Every mode assert in `test_findings.py` changes, including three tests added after the baseline was recorded (lines 776, 835, 902). |
| `rmtree(path)` in `conftest.py`: `shutil.rmtree` with an `onexc` handler that makes the entry and its parent writable and retries | `onerror` | `onerror` is deprecated from Python 3.12 (`requires-python >=3.12`). Making the parent writable also covers a read-only folder on POSIX. |
| `make_repo` writes bytes, and the other fixtures that hold `\r\n` (`test_known.py`, `test_findings.py`'s accepted list) do too | Only the secrets-scan fixture | Text mode on Windows turns `\n` into `\r\n` everywhere, so fixtures differed from Linux. Bytes make them the same on every OS. |
| `test_stacks`: on Windows, leave out `b"q/` (Windows forbids `"`) and `d\e/` (Windows reads `\` as a folder separator), expecting 4 unsafe names instead of 6 | Staging those names in the index only | `scope.py`'s install detection isn't known not to look at the files on disk; the four other unsafe names still test quoting on Windows. |
| `test_skips_names_that_are_not_utf8`: write the index entry through `git update-index --index-info` on stdin | Skipping on Windows | The failure is in the fixture: Windows can't put non-UTF-8 bytes on a command line, but stdin carries bytes. `scope.py` only reads `git ls-files -z`, so no checkout is needed. |
| Symlink tests call `skip_unless_git_keeps_symlinks(tmp_path)`: it skips when `os.symlink` fails (Developer Mode or admin needed), and when a committed link, cloned with `git clone --no-local`, comes back as a plain file (`core.symlinks=false`), each with its reason | Skipping only when `os.symlink` fails | An elevated CI runner can create links while Git for Windows still checks them out as files, which is the second half of the throwaway rows. |
| On a Python whose `tempfile` retries a refused `mkstemp` up to `os.TMP_MAX` (3.12 on Windows: 2**31 tries, since `os.access` can't see the deny ACL), the two `post.py` lock tests skip with that reason (`MKSTEMP_SPINS_ON_A_LOCKED_DIR`). The lock helper's own test uses `open(…, "x")`, which fails at once. | Letting them run (the job hangs to its 30-minute timeout); fixing `post.py` here | 3.13 and 3.14 cap the retries at 20 (`Lib/tempfile.py`). The hang is a real `post.py` bug on Windows with 3.12, so it is a ticket, not a test change. |
| CI: `ci.os` in `.sdlc/config.json` lists `ubuntu-latest` and `windows-latest`, and `sdlc-verify.yml`'s matrix matches it, as the generator writes it; nothing else changes. The owner's request is the go-ahead `sdlc-ci.md` asks for. | Editing only the workflow, which `/sdlc:upgrade` would regenerate without the runner; pinning `core.autocrlf` | The scaffold builds the matrix from `ci.os`. The scripts handle Git for Windows' system config on purpose, so changing it in CI would hide that. |

## Acceptance criteria

- **AC-001** The fake `gh` is not a `#!` script. Run by the name `gh`, it logs each argument exactly as given, including `$(…)`, backticks, quotes, `& | < > ^ %` and non-ASCII, and runs none of them.
- **AC-002** The `fake_gh` environment moves `USERPROFILE` with `HOME`.
- **AC-003** `rmtree` removes a tree holding a read-only file and a read-only folder with a file in it.
- **AC-004** `mode_is` compares POSIX permission bits exactly on POSIX and is true on Windows.
- **AC-005** `lock_dir` makes a folder refuse a new file until `unlock_dir`.
- **AC-006** `skip_unless_git_keeps_symlinks` skips, saying why, when symlinks can't be created or when git checks a committed link out as a plain file, and lets the test run otherwise.
- **AC-007** CI runs lint and the full suite on `windows-latest` as well as `ubuntu-latest`.
- **AC-008** (manual) The 19 rows in `.sdlc/baseline.md` pass, or skip with their stated reason, on the `windows-latest` job.
- **AC-009** (review r1, H1, M1) When `throwaway.py` removes a copy while ignoring errors, an entry it can't remove doesn't stop it removing the rest. Without ignoring, the first error still raises. On Windows a refused unlink of a read-only entry is retried after clearing the flag, but never through a link or reparse point, and a retry that fails again raises its own error.
- **AC-010** (review r1, L3) Bytes from `gh` that aren't valid in the reading encoding don't turn `post.py` into a traceback, either from `gh auth status` or from `gh issue create`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_portable_fixtures.py › test_fake_gh_is_an_interpreter_and_keeps_arguments_exact | `uv run pytest tests/test_portable_fixtures.py -k test_fake_gh_is_an_interpreter_and_keeps_arguments_exact` |
| AC-002 | tests/test_portable_fixtures.py › test_fake_gh_moves_userprofile_with_home | `uv run pytest tests/test_portable_fixtures.py -k test_fake_gh_moves_userprofile_with_home` |
| AC-003 | tests/test_portable_fixtures.py › test_rmtree_removes_read_only_entries | `uv run pytest tests/test_portable_fixtures.py -k test_rmtree_removes_read_only_entries` |
| AC-004 | tests/test_portable_fixtures.py › test_mode_is_exact_on_posix_and_true_on_windows | `uv run pytest tests/test_portable_fixtures.py -k test_mode_is_exact_on_posix_and_true_on_windows` |
| AC-005 | tests/test_portable_fixtures.py › test_lock_dir_refuses_new_files_until_unlocked | `uv run pytest tests/test_portable_fixtures.py -k test_lock_dir_refuses_new_files_until_unlocked` |
| AC-006 | tests/test_portable_fixtures.py › test_symlink_probe_skips_with_its_reason | `uv run pytest tests/test_portable_fixtures.py -k test_symlink_probe_skips_with_its_reason` |
| AC-007 | tests/test_portable_fixtures.py › test_ci_runs_the_suite_on_windows | `uv run pytest tests/test_portable_fixtures.py -k test_ci_runs_the_suite_on_windows` |
| AC-008 | manual | Windows only: no Windows machine here. The first `windows-latest` run checks it, and only then do the rows leave the baseline. |
| AC-009 | tests/test_throwaway_rmtree.py | `uv run pytest tests/test_throwaway_rmtree.py` |
| AC-010 | tests/test_post.py › test_odd_bytes_from_gh_never_become_a_traceback | `uv run pytest tests/test_post.py -k test_odd_bytes_from_gh_never_become_a_traceback` |

## Must never break

- No test can reach a logged-in real `gh` (`test_tests_can_never_reach_a_logged_in_real_gh`, the `no_real_gh` guard).
- The `post.py` tests still prove a title like `$(touch pwned)` is passed as one argument and runs nothing.
- The suite stays green on macOS and Linux, with no test newly skipped there.

## Failure modes

- A Windows half that reasoning got wrong (the copied `python.exe`, `icacls` rights, git's symlink checkout): the first CI run shows it; its baseline row stays until then.
- Rows recorded on 2026-11-06 name only the first failure each test hit, and tests added since were never run on Windows. The first Windows run may show failures not in the baseline; each is a fixture fix of the same kind, or a new baseline row with the owner's OK.

- `make_repo` now writes LF on Windows for every test that builds a repo, not only the CRLF row; Linux already ran them that way.

## Out of scope

- `post.py` spinning on a locked drafts folder on Windows with Python 3.12 (`tempfile` retries `mkstemp` 2**31 times): a product ticket.

- Removing the baseline rows (after the first green Windows run) and editing `docs/sdlc/todo.md`.
- Product code under `scripts/`, except two real Windows bugs the first `windows-latest` run (actions run 45018336646) exposed once the fixtures stopped hiding them:
  - `post.py` was the only script that didn't switch stdout and stderr to UTF-8, so on Windows it wrote `ü` and `²` in the ANSI code page and the caller, reading UTF-8, lost its stderr. It now does what every other script does.
  - `throwaway.py` couldn't remove a copy it had cloned and then refused (escaping symlinks, a failed seal), because git leaves its object files read-only on Windows, so the refusal turned into "couldn't copy: Access is denied". Its removals now go through `_rmtree`, which clears the read-only flag and retries. It never acts on a link, and only runs on a folder this script just made, so nothing else can be running in it.

## Review

No review ran: low risk, no trigger fired (tests and CI only, no product code, empty Public Surface); every AC with a test red then green (verify.py). AC-008 (manual): the 19 baseline rows are verified only by reasoning until the first windows-latest CI run on this PR; baseline rows stay until that run shows them passing. Ticket: post.py hangs instead of refusing a locked drafts folder on Windows with Python 3.12 (out of scope, product code).

The product fixes in `post.py` and `throwaway.py` triggered a code review, run by the coordinator:
- r1 FAIL on H1 (`.sdlc/.work/findings/2026-11-22-m-windows-suite/code-reviewer-r1.md`).
- r2 PASS, no high or medium (`.sdlc/.work/findings/2026-11-22-m-windows-suite/code-reviewer-r2.md`). Its two lows are tickets in `docs/sdlc/todo.md`: L-a, share `scratch.py`'s Windows read-only helper; L-b, the Windows-side tests lean on monkeypatching and there is no WinError 32 test.

Code review r1 of the `scripts/` changes: FAIL on H1. Fixed test-first (AC-009, AC-010):
- H1: `_rmtree(ignore_errors=True)` stopped at the first entry it couldn't remove. It now skips that entry and removes the rest, while callers that don't ignore still get the first error.
- M1: the Windows retry decides from one `lstat` and never chmods a link or reparse point.
- L2: added tests for the link guard and for a retry that fails again.
- L3: `post.py` no longer decodes `gh auth status`, and decodes `gh issue create` with `errors="replace"`.
- M2 (bounded retry for WinError 32): not seen in CI, so not done.
- L1 (refusal reason lost when cleanup fails): a ticket in `docs/sdlc/todo.md`.

Baseline pruned: 17 of the 19 rows pass on windows-latest (CI run 45020995450, Python 3.12.10), so they are removed: both test_known.py rows, test_post.py's test_files_named_drafts_once and test_refuses_before_filing_and_keeps_partial_progress, both test_drafts.py rows, the four test_findings.py rows, test_secrets_scan.py's row, test_stacks.py's row, both test_scope.py rows, and the three test_throwaway.py symlink rows. Kept, with the reason updated: test_refuses_odd_numbers_duplicates_and_unusable_record and test_shows_url_when_recording_fails_after_filing, which skip on Python 3.12 (tempfile retries a refused mkstemp 2^31 times) and pass on 3.13+.
