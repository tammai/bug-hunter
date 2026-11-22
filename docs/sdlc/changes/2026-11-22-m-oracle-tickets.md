# `oracle.py` part 2 review tickets: citations, scope, git reads

## Why

**Request (verbatim):** "Do the todo item "`oracle.py` (part 2) review tickets" from docs/sdlc/todo.md: the Citations and Scope groups (correctness), plus Efficiency and Reuse tickets that don't touch scripts/scope.py, scripts/drafts.py, scripts/contracts.py or scripts/findings.py (those stay tickets). Feature name 2026-11-22-<track>-oracle-tickets. Prove each bug with a failing test first."

`/hunt --oracle` scopes a hunt by a spec's features (`scripts/oracle.py`), and `drafts.py check` and `finding_v1.py` judge drafts by what Expected cites. A code review of 8dcab0e (meant for part 3) left 23 unverified findings on part 2, ticketed in `docs/sdlc/todo.md` by [2026-11-08-m-review-followups](2026-11-08-m-review-followups.md). Each fixed one below was first shown failing by its own test on `main` (635113a).

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| A draft marked `Oracle: spec-gap` that also cites a criterion or rule of the spec is classed by the citation (`build-defect`); `spec-gap` needs the mark and no citation. `with_reference` reads the same class. | Refusing the draft in `drafts.py check` | `drafts.py` is owned by a parallel change; and the citation is the stronger evidence: the spec does cover the behaviour. |
| With no feature having source files, `oracle.py scope` exits 1 with one `error:` line, with or without `--live`, as `scope.py` does. | The empty plan (exit 0) that part 2 chose and `test_live_with_no_source_files_is_an_empty_plan` pinned | The ticket names the exit 0 as the defect; `hunt.md` already stops on a non-zero exit. That test is replaced by `test_no_source_files_is_one_error_line`. |
| A criterion's lock level counts only when its active story line hashes to the lock's `text_sha256` (`contracts.criterion_text_sha256`, C3); a changed line, a missing line or an unreadable story gives level 0. | Keeping the level when the line can't be found | CONTRACTS.md C3: "`text_sha256` mismatch → level drops to 0 until re-verified". A level that can't be checked isn't evidence. |
| Story criteria are parsed with contracts' own `CRIT_LINE`/`ACTIVE` (C1), so `~~**ID** …~~` lines are removed criteria: no text, no hash, and their `domain.md §` citations don't count. | A fourth criterion regex | One grammar with the producer of the lock. |
| `CRITERION` also matches a standalone `AC-nnn` (3+ digits, C1), not after a word character, `.` or `-`. The change-file `→ ID` link uses the same pattern. | — | The C1 ID rule and the lock schema allow both forms. `drafts.py check` imports `CRITERION`, so an Expected citing `AC-001` against an rspec lock now reads as an unknown criterion. |
| A commit belongs to a change when its message names the change file the way sdlc writes it: a `Record: <change>` line (with or without ` in the workbench (…)`), or a subject ending `(<change>)`. A merge commit's files are its first-parent diff. | Any `--grep` hit; requiring the commit to touch the change file | The forms are `ship.py`'s (`Record:`) and the part-commit rule (`… (<change>)`). Touching the change file would drop backlog part commits. |
| History is read in three `git` calls per run, whatever the number of features: all messages (`-z --format=%H%x00%B`), the named commits' numstat (`--stdin --no-walk --diff-merges=first-parent`), and the all-history numstat of state-listed files. All with `-z`. The all-history walk keeps merges out, so merged lines aren't counted twice. | One call per feature (today) | Efficiency tickets; `-z` closes the C-quoted path ticket on the same code. |
| `oracle.py` prints the same two install warnings as `scope.py` (non-UTF-8 names, unsafe lockfile folders), by repeating `scope._main`'s few lines with `scope._safe_folder` and `scope.STACKS`. | Moving them into a shared `scope.py` function | `scope.py` is owned by a parallel change; the duplication is a new reuse ticket. |
| `_section` and `domain_headings` skip headings inside code fences, with `drafts.fenced`. | A new fence parser | Import only; `drafts.py` is not edited. |
| Reuse: `cited_rules` goes (`finding_v1` calls `rule_citations(...)[0]`). `_repo_path` stays. | Replacing `_repo_path` with `scope._relative` | `cited_rules` needs no owned file. `scope._relative` isn't equivalent: it resolves an absolute path (following links, touching the filesystem) the hunted repo wrote, and maps `docs_dir: "."` to the default `docs/sdlc` (`test_a_docs_dir_of_dot_puts_change_files_in_changes`). |

How the build runs: inline, one part.

## Acceptance criteria

- **AC-001** Citations: `rule_citations` counts a rule citation whose file name is backticked, or followed by a comma before the section sign, or both, as citing that heading.
- **AC-002** Citations: a bold or backticked spec-gap line (`**Oracle: spec-gap**`, `` `Oracle: spec-gap` ``, `**Oracle:** spec-gap`, ``Oracle: `spec-gap` ``) marks the draft a spec gap; `spec-gaps` doesn't.
- **AC-003** Citations: given a draft marked `Oracle: spec-gap` whose Expected cites a lock criterion (or a `domain.md` rule), `finding_v1.py write --oracle` writes `class` `build-defect`, route `sdlc`, with `criterion` (or `rule`) set.
- **AC-004** Citations: `CRITERION` matches standalone `AC-001` but not `XAC-002` or `AC-01`; a lock of `AC-nnn` IDs gives parts with each criterion's story text and level.
- **AC-005** Citations: a struck-through story criterion (`~~**ID** …~~ reason`) gives no criterion text and its `domain.md §` citations aren't in `domain_rules`.
- **AC-006** Scope: when no feature has source files, `oracle.py scope` (with or without `--live`) prints one `error:` line and exits 1.
- **AC-007** Scope: a criterion whose story line no longer hashes to its `text_sha256` is reported at level 0, counts as below level 2, and its feature ranks with the unproven ones.
- **AC-008** Scope: a commit whose message only mentions a change file (not as `Record: <change>` or a `(<change>)` subject) adds no files; a `Record:` line does.
- **AC-009** Scope: a change file links a criterion only by `→ ID` under its `## Acceptance criteria`.
- **AC-010** Scope: a merge commit that names a change lists the files its merge brought in.
- **AC-011** Scope: tracked paths git would C-quote (a `"` in the name) are matched in the commit fallback and in line counts. (Skipped on Windows, where a file name can't hold `"`.)
- **AC-012** Scope: a `## …` line inside a code fence is not a heading for `_section` or `domain_headings`.
- **AC-013** Scope: `oracle.py scope` prints `scope.py`'s warnings for tracked names that aren't UTF-8 and for a lockfile in an unsafe folder.
- **AC-014** Efficiency: `build` runs `git` a fixed number of times (at most 3), the same for 3 features as for 7.
- **AC-015** Efficiency: integration markers are read only for the parts kept after `--max`/`--budget`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_oracle.py › test_rule_citations_read_a_backticked_file_name_and_a_comma | `uv run pytest tests/test_oracle.py -k test_rule_citations_read_a_backticked_file_name_and_a_comma` |
| AC-002 | tests/test_oracle.py › test_a_bold_or_backticked_spec_gap_line_counts | `uv run pytest tests/test_oracle.py -k test_a_bold_or_backticked_spec_gap_line_counts` |
| AC-003 | tests/test_finding_v1.py › test_a_spec_gap_draft_that_cites_a_criterion_is_a_build_defect | `uv run pytest tests/test_finding_v1.py -k test_a_spec_gap_draft_that_cites_a_criterion_is_a_build_defect` |
| AC-003 | tests/test_oracle_followups.py › test_a_spec_gap_draft_that_cites_a_criterion_is_covered_against_the_reference | `uv run pytest tests/test_oracle_followups.py -k test_a_spec_gap_draft_that_cites_a_criterion_is_covered_against_the_reference` |
| AC-004 | tests/test_oracle.py › test_standalone_criterion_ids_are_criteria | `uv run pytest tests/test_oracle.py -k test_standalone_criterion_ids_are_criteria` |
| AC-005 | tests/test_oracle.py › test_struck_through_criteria_are_not_read | `uv run pytest tests/test_oracle.py -k test_struck_through_criteria_are_not_read` |
| AC-006 | tests/test_oracle.py › test_no_source_files_is_one_error_line | `uv run pytest tests/test_oracle.py -k test_no_source_files_is_one_error_line` |
| AC-007 | tests/test_oracle.py › test_an_edited_criterion_drops_to_level_0 | `uv run pytest tests/test_oracle.py -k test_an_edited_criterion_drops_to_level_0` |
| AC-008 | tests/test_oracle.py › test_a_commit_that_only_mentions_a_change_file_isnt_its_commit | `uv run pytest tests/test_oracle.py -k test_a_commit_that_only_mentions_a_change_file_isnt_its_commit` |
| AC-009 | tests/test_oracle.py › test_a_change_file_links_criteria_only_in_its_acceptance_criteria | `uv run pytest tests/test_oracle.py -k test_a_change_file_links_criteria_only_in_its_acceptance_criteria` |
| AC-010 | tests/test_oracle.py › test_a_merge_commit_naming_a_change_lists_its_files | `uv run pytest tests/test_oracle.py -k test_a_merge_commit_naming_a_change_lists_its_files` |
| AC-011 | tests/test_oracle.py › test_paths_git_would_quote_still_match | `uv run pytest tests/test_oracle.py -k test_paths_git_would_quote_still_match` |
| AC-012 | tests/test_oracle.py › test_headings_inside_code_fences_are_text | `uv run pytest tests/test_oracle.py -k test_headings_inside_code_fences_are_text` |
| AC-013 | tests/test_oracle.py › test_install_warnings_are_printed_in_oracle_mode | `uv run pytest tests/test_oracle.py -k test_install_warnings_are_printed_in_oracle_mode` |
| AC-014 | tests/test_oracle.py › test_git_runs_a_fixed_number_of_times | `uv run pytest tests/test_oracle.py -k test_git_runs_a_fixed_number_of_times` |
| AC-015 | tests/test_oracle.py › test_integrations_are_read_only_for_kept_parts | `uv run pytest tests/test_oracle.py -k test_integrations_are_read_only_for_kept_parts` |

The test fixture's lock now carries real `text_sha256` values (it held `"0" * 64`), so existing ranking tests keep their levels under AC-007.

## Must never break

- Spec and repo files are still read only through `_inside`/`_read`, never through a link (`test_spec_files_are_not_read_through_symlinks`, `test_a_story_path_outside_the_spec_is_not_read`); git-reported paths are used only when tracked.
- Ranking, `--max`, `--budget` and `--live` output stay as before for a spec whose hashes match (`test_ranking_puts_unproven_criteria_then_changed_lines_first`, `test_live_keeps_only_parts_serving_http`).
- `drafts.py check --oracle` still accepts and refuses the same F-form drafts (`test_expected_cites_the_spec_or_marks_a_spec_gap`).
- Every failure is one `error:` line, never a traceback (`test_a_bad_oracle_is_one_error_line`).

## Failure modes

- Untrusted input (the lock, story files, the hunted repo's history and file names): file names with quotes, tabs or non-UTF-8 bytes → AC-011, AC-013; malformed lock fields (`text_sha256` missing or not a string) → level 0, AC-007.

## Out of scope

Left as tickets, each needing a file another parallel change owns:

- **Scope:** the verifier's "Cited criteria" come only from the part's own criteria while `drafts.py check` accepts any lock ID. The fix is to restrict the check to the part's criteria (`drafts.py`), or give the verifier every cited criterion's text; a `hunt.md`-only fix can't supply text for a `not_hunted` feature.
- **Efficiency:** `classify_by_oracle` parses the spec twice; the fix is for `drafts.oracle_problems` to return what it loaded.
- **Reuse:** the section parsers (`drafts.expected_body`, `finding_v1._sections`, `oracle._section`, `contracts._section`); the max, budget and live cuts duplicated from `scope.py`; `_repo_path` beside `scope._relative` (not equivalent, see Decisions: a shared text-only helper would need `scope.py`); and, new here, the install warnings repeated from `scope._main`.
