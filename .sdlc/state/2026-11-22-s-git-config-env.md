# 2026-11-22-s-git-config-env
Status: done
Process: 3
Track: S   (footprint: 2 files)
Risk: high
Top model: opus
Base: e53f3a9
Owner: tammai.it@gmail.com
Tool: claude-code
Verified: e53f3a9 tree 212bb1d10ed8ccba94410c25ed88755b57d5271f
Current: Stage 4 – Ship

## Tasks
1. **Unset git config passed through the environment** — AC-001
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`

## Public Surface
- none

## Test lock
- `tests/test_isolate.py` sha256:bcc1e1047cff89504415e4b542ce9ef320373731356a157a842761f09fcd36ba

## Gate log
- 2026-11-22 Stage 1: pass
- 2026-11-22 Stage 4: baseline failures waived (listed in .sdlc/baseline.md): tests/test_drafts.py::test_dir_is_outside_target_named_after_origin, tests/test_drafts.py::test_dir_names_never_collide_or_escape, tests/test_findings.py::test_audit_folder_and_numbering, tests/test_findings.py::test_script_outputs_become_findings, tests/test_findings.py::test_report_and_inventory, tests/test_findings.py::test_known_secrets_are_withheld_and_code_is_not, tests/test_known.py::test_lists_open_issues_and_earlier_drafts, tests/test_known.py::test_titles_are_cleaned_and_a_full_page_is_flagged, tests/test_post.py::test_files_named_drafts_once, tests/test_post.py::test_refuses_before_filing_and_keeps_partial_progress, tests/test_post.py::test_refuses_odd_numbers_duplicates_and_unusable_record, tests/test_post.py::test_shows_url_when_recording_fails_after_filing, tests/test_scope.py::test_skips_names_that_are_not_utf8, tests/test_scope.py::test_live_keeps_only_parts_serving_http, tests/test_secrets_scan.py::test_finds_secrets_without_printing_them, tests/test_stacks.py::test_install_steps_are_exact_and_unsafe_folders_get_none, tests/test_throwaway.py::test_refuses_symlinks_out_of_the_copy_and_a_used_dest, tests/test_throwaway.py::test_copy_from_a_base_is_independent_and_checked, tests/test_throwaway.py::test_copy_from_a_base_falls_back_when_cp_fails
- 2026-11-22 Stage 2: pass — security review round 1 PASS; S1 filed as todo

## Deviations
-

## Open questions
-
