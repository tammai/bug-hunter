# 2026-11-22-m-windows-suite
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-windows-suite.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 10 files)
Risk: low
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: 5eea35f
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 89ba90b tree e8d8906348ab59652abbcd7b5302094e007380ab
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [x] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

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
- `tests/test_post.py` sha256:1600a56d56b7693505fa54c3e2fa17ed9804dcdc0fcb7c02fd4c2f1ee7e3828d
- `tests/test_throwaway_rmtree.py` sha256:34ba882d2a6087b496e7c92371fc4ee819d945e3fd3e104583fc399e60afe040

## Gate log
- 2026-11-22 Stage 1: pass — plan not stopped for approval: low-risk M
- 2026-11-22 review deferred: coordinator runs every lane's reviews together after the build; committed on the branch, not pushed
- 2026-11-22 Base What: moved from 635113a to 7790f3e. Why: rebased onto main after PR #44 (C3) merged. Effect: diff and drift checks cover only this change.
- 2026-11-22 Stage 2: pass — no review: no trigger fired
- 2026-11-22 Stage 4: pass — back from review r1 (FAIL H1): fixing H1, M1, L2, L3 test-first
- 2026-11-22 Stage 2: pass — r1 fixes verified; round 2 check is the coordinator's
- 2026-11-22 Stage 3: pass

## Deviations
- 2026-11-22 test-change tests/test_portable_fixtures.py What: the lock test's finally called a misspelled name (unconftest.lock_dir) and now calls conftest.unlock_dir. Why: a typo from rewriting the imports into attribute access; the test was red for the missing helper either way, not weakened.
- 2026-11-22 Task 2 What: also changed mode asserts at test_findings.py:775/834/901 and the CRLF accepted-list fixture at test_findings.py:705, which no baseline row names. Why: same Windows failure class in tests added after the baseline was recorded; left alone they turn the new runner red. Effect: none on macOS/Linux.
- 2026-11-22 test-change tests/test_portable_fixtures.py What: AC-001 runs the fake by its resolved path; AC-005 checks the lock with open(x) instead of mkstemp; AC-006 asserts the core.symlinks case only where links can be created, after the no-rights case. Why: on Windows a child's env doesn't steer CreateProcess's lookup of gh; 3.12's mkstemp spins on a denied folder; an account without link rights hits the other reason first. Not weakened: the same behaviours are asserted.
- 2026-11-22 Task 3 What: .sdlc/config.json gets ci.os = [ubuntu-latest, windows-latest]. Why: the scaffold builds sdlc-verify.yml's matrix from it, so /sdlc:upgrade would otherwise drop the runner. Effect: none locally.
- 2026-11-22 Task 2 What: the two post.py lock tests skip on a Python whose tempfile.TMP_MAX > 100 on Windows (3.12). Why: tempfile retries a refused mkstemp 2**31 times there, so post.py would hang the job. Effect: none on macOS/Linux or on Windows with 3.13+; the post.py bug is a ticket.
- 2026-11-22 scripts/post.py What: _main switches stdout and stderr to UTF-8, like every other script. Why: windows-latest run 45018336646 failed test_refuses_before_filing_and_keeps_partial_progress and test_refuses_odd_numbers_duplicates_and_unusable_record with stderr None (UnicodeDecodeError on 0xfc/0xb2): post.py wrote ü and ² in cp1252. Those CI failures are the failing tests; macOS can't show them. Effect: none on POSIX.
- 2026-11-22 scripts/throwaway.py What: every removal of the copy goes through _rmtree, which on Windows clears the read-only flag on a refused unlink/rmdir and retries, never on a link. Why: windows-latest run 45018336646 failed test_refuses_symlinks_out_of_the_copy_and_a_used_dest with 'couldn't copy: [WinError 5] Access is denied' on .git/objects/pack/*.idx: refusing a clone couldn't delete it. That CI failure is the failing test. Effect: none on POSIX (the handler re-raises there).
- 2026-11-22 Correction to the scripts/throwaway.py line above: its 'Effect: none on POSIX' was wrong. The handler re-raised every case it didn't handle, so _rmtree(ignore_errors=True) stopped at the first failure on POSIX too (review r1 H1). Fixed: _clear_read_only is module-level and decides from one lstat (no link or reparse point is chmod-ed, M1); _rmtree's onexc skips the entry when ignoring and re-raises otherwise. Tests: tests/test_throwaway_rmtree.py (AC-009).
- 2026-11-22 scripts/post.py What: gh auth status is no longer decoded (only its exit code is read), and gh issue create is decoded with errors=replace (review r1 L3). Test: test_odd_bytes_from_gh_never_become_a_traceback (AC-010), through a FAKE_GH_STDERR_HEX knob in tests/conftest.py's fake gh.
- 2026-11-22 docs/sdlc/todo.md What: the review r1 L1 ticket (refusal reason lost when cleanup fails) is an open item. Why: the coordinator triaged L1 as a ticket.
- 2026-11-22 tests/test_oracle.py What: merged origin/main (fdd1072) into the branch; its new test_install_warnings_are_printed_in_oracle_mode put a non-UTF-8 name on a bytes command line, which Windows can't carry (windows-latest run 45023197510). It now writes the index entry through git update-index --index-info on stdin, as test_scope.py does. Why: the PR's merge ref runs main's tests on Windows. Effect: fixture only; oracle.py untouched.
- 2026-11-22 Base What: moved from 7790f3e to fdd1072 after merging origin/main into the branch. Why: main gained the oracle lane's changes (scripts/oracle.py, scripts/finding_v1.py and their tests), which aren't this feature's and showed as drift against the old Base. Effect: the drift check sees only this feature's files.
- 2026-11-22 test-change tests/test_isolate.py What: test_a_variable_bash_cant_unset_stops_isolation now reads the child's raw Windows environment block (GetEnvironmentStringsW) and expects the bang-C drive name there under its Windows spelling, equals-C; child_env takes the child code as an optional argument. Why: a windows-latest diagnostic run (45027927588, temporary test since removed) showed MSYS hands that name to native programs as equals-C with the value unchanged, and Python's nt.environ hides names starting with an equals sign, so the old lookup could never succeed; isolate.py exits 0 and leaves the name alone. Effect: POSIX unchanged; isolate.py unchanged. The test came from main (isolate lane, b4d953c) via the merge of origin/main.
- 2026-11-22 Base What: moved from fdd1072 to 5eea35f after merging origin/main again. Why: main gained other lanes' changes that showed as drift against the old Base. Effect: the drift check sees only this feature's files.

## Open questions
-
