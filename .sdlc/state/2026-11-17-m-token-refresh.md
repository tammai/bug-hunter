# 2026-11-17-m-token-refresh
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-17-m-token-refresh.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 5 files)
Risk: high   (secrets (account tokens) and a command run from targets.json)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-17
Base: 223de35
Owner: tammai.it@gmail.com
Tool: claude-code
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline

## Handoff
- load_target is also called by drafts.py:352 and finding_v1.py:629; it must parse refresh but never run it
- masker is cached per handler in masker[0] (live_proxy.py _handler); rebuild it after each refresh
- stub_server logs request headers, redacting secret-word names; use a plain header name in tests to see which token arrived

## Tasks
1. **Refresh command: load, run, retry on 401, mask** — AC-001 AC-002 AC-003 AC-004 AC-005 AC-006 AC-007 AC-008
   - Files: `scripts/live_proxy.py`, `tests/test_live_proxy.py`
2. **Docs and todo** — AC-009
   - Files: `commands/hunt.md`, `README.md`, `docs/sdlc/todo.md`

## Public Surface
- config `targets.json refresh` — AC-001

## Test lock
- `tests/test_live_proxy.py` sha256:0acd30e60decd5d4dd01eff3843050148ccd0195ac60edf72b43195e64a8cb48

## Gate log
- 2026-11-17 Stage 1: pass — approved by owner (high-risk M)
- 2026-11-17 verify: only the test step failed; all 19 failures are listed in .sdlc/baseline.md (Windows only); every AC passes, lint clean
- 2026-11-17 Stage 2: pass — verify failed only on the 19 baseline tests (Windows only)
- 2026-11-17 review: owner chose security + code (Risk high, Public Surface)
- 2026-11-17 Stage 3: fail — round 1: security S1-S4,S8 and code CR1-CR9,CR11 to fix
- 2026-11-17 verify after round-1 fixes: only the 19 baseline tests fail (compared by name); every AC passes, lint clean
- 2026-11-17 Stage 2: pass — round-1 fixes in; verify fails only on the 19 baseline tests
- 2026-11-17 Stage 3: fail — round 2: security N1, N3 high; owner chose one more fix round; code r2 medium/low bugs fixed too
- 2026-11-17 Stage 2: pass — round-2 fixes in; verify fails only on the 19 baseline tests (compared by name)
- 2026-11-17 Stage 3: pass — security r3 PASS (owner-approved extra round), code r2 PASS; r3 medium fixed; tickets in Review
- 2026-11-17 Stage 4: baseline failures waived (listed in .sdlc/baseline.md): tests/test_drafts.py::test_dir_is_outside_target_named_after_origin, tests/test_drafts.py::test_dir_names_never_collide_or_escape, tests/test_findings.py::test_audit_folder_and_numbering, tests/test_findings.py::test_script_outputs_become_findings, tests/test_findings.py::test_report_and_inventory, tests/test_findings.py::test_known_secrets_are_withheld_and_code_is_not, tests/test_known.py::test_lists_open_issues_and_earlier_drafts, tests/test_known.py::test_titles_are_cleaned_and_a_full_page_is_flagged, tests/test_post.py::test_files_named_drafts_once, tests/test_post.py::test_refuses_before_filing_and_keeps_partial_progress, tests/test_post.py::test_refuses_odd_numbers_duplicates_and_unusable_record, tests/test_post.py::test_shows_url_when_recording_fails_after_filing, tests/test_scope.py::test_skips_names_that_are_not_utf8, tests/test_scope.py::test_live_keeps_only_parts_serving_http, tests/test_secrets_scan.py::test_finds_secrets_without_printing_them, tests/test_stacks.py::test_install_steps_are_exact_and_unsafe_folders_get_none, tests/test_throwaway.py::test_refuses_symlinks_out_of_the_copy_and_a_used_dest, tests/test_throwaway.py::test_copy_from_a_base_is_independent_and_checked, tests/test_throwaway.py::test_copy_from_a_base_falls_back_when_cp_fails
- 2026-11-17 deployed v0.6.0 to GitHub release: smoke test pass (install only; live run skipped by owner)

## Deviations
- 2026-11-17 test-change tests/test_live_proxy.py What: the minted header in the tests is X-Seat, not X-Session. Why: stub_server.py redacts header names with secret words (session) in its log, so the test could not see which token arrived. Effect: none on what the tests prove.
- 2026-11-17 test-change tests/test_live_proxy.py What: round-1 fixes: tests for throttle from the start-up mint (--refresh-gap), static-account 401s, forwarded log field, concurrent 401s with rate pacing, positional errors, deep JSON, a program planted in the repo, the same-origin check before minting, one Basic warning; slow timeout case dropped. Why: security S1-S4,S8 and code CR1-CR9; the testing rule caps failure matrices. Effect: AC-002-AC-008 tests are stricter; the 60 s timeout is no longer exercised by a test.
- 2026-11-17 test-change tests/test_live_proxy.py What: round-2 fixes: a replaced static Alice stays masked and merges case-insensitively; the planted program is refused via the repo on PATH from another folder; a folder as the program is not called the repo; throttled 401s after a failed mint carry the note; an account a later mint leaves out keeps its token. Why: security N1-N4, N8, N9 and code R2-1-R2-12. Effect: stricter AC-001, AC-004, AC-005, AC-006 tests; one new test.
- 2026-11-17 test-change tests/test_live_proxy.py What: added test_slow_refresh_command_is_stopped_with_its_child (in-process, REFRESH_TIMEOUT patched to 1 s). Why: security round 3 M2, the timeout and kill-tree path had no test. Effect: AC-005's timeout kind is covered again; no existing assertion changed.
- 2026-11-17 test-change tests/test_live_proxy.py What: the planted program copy is made executable. Why: CI on Linux: shutil.which skips non-executable files, so the test never reached the repo refusal there. Effect: the planted case proves the refusal on POSIX too.

## Open questions
-
