# bug-hunter 0.4 part 2: oracle scoping, oracle briefs, risk ranking

## Why

**Request (verbatim):** implement docs/specs/rebuild-upgrade/04-bug-hunter.md, part 2 only.

Part 2 is B1 of [docs/specs/rebuild-upgrade/04-bug-hunter.md](../../specs/rebuild-upgrade/04-bug-hunter.md): `/hunt --oracle <spec>` hunts a rebuild feature by feature, judges each bug against the spec (criteria and `domain.md` rules) instead of the builder's own code and docs, and spends `--max`/`--budget` on the riskiest features first. Built on part 1 (branch `2026-11-08-m-finding-v1-budget`, 7e21c61).

**The user's words:** orchestrator answers (Orca, 2026-11-08, msg_e6417e8d9db0: "All as proposed"):
- Q1 Inputs: `--oracle <spec>` is a folder with `criteria.lock.json` (C3). Story = `<spec>/<lock file>`; domain rules = the `domain.md §<Section>` references in the story, read from `<spec>/domain.md`; operations = operationIds in `<spec>/openapi.json` whose `x-features` include the feature; a missing file gives an empty input. Source files: sdlc state files whose `## Criteria` lists a feature's criterion (or change files citing `→ <ID>`), then those states' `## Tasks` backticked file lists (sdlc 3.x keeps Tasks in the state file: a deviation from B1's wording). Fallback: `git log --name-only` of commits whose message names one of those change files. Only tracked source files `scope.py` would hunt, at most 8 per feature.
- Q2 Parts: one per feature; over 8 files keeps the 8 with most changed lines (path order on ties) and lists the rest; a feature with no source file is listed as not hunted.
- Q3 Ranking key: any active criterion at level < 2 first; then changed lines (added + deleted, `git log --numstat` over the part's files, over the commits found in Q1, or all history of those files when only Tasks lists were used); then failure modes (story lines under `## Failure modes` other than "none"); then feature ID. `--max` and `--budget` cut after ranking; the preview shows the ranking and the parts left out.
- Q4 Brief and Expected: hunters get their part's story text, cited domain sections, operations and criteria (with level). Expected cites a criterion ID from the lock or `domain.md §<Section>`; a wrong behaviour nothing covers is a spec-gap candidate: Expected says `No criterion or rule covers this` and an `Oracle: spec-gap` line goes under the title. `drafts.py check --oracle <spec>` fails an unknown ID or §, and an uncited Expected without that line. The verifier also gets the cited criterion's text.
- Q5 finding-v1: a cited criterion → `build-defect`, `criterion` = ID; a domain rule only → `build-defect`, `rule` = `domain.md §Section`; spec-gap → `spec-gap` (route rspec), both null; `verified_by` still `reproduced`.
- Q6 Scope: `scripts/oracle.py`, `drafts.py --oracle`, `finding_v1.py --oracle`, `/hunt --oracle` wiring, prompts, tests on a small fixture; no live hunt; `departures.yaml` (B5) not read.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| New `scripts/oracle.py scope` emits the same part shape as `scope.py` (plus the oracle fields), reusing its helpers | Extending `scope.py` | Folder scoping and feature scoping share nothing but helpers; `/hunt` reads both the same way |
| A cited domain rule is a `## ` heading of `domain.md` that the story names as `§<heading>` | Free-text parsing of `§…` | Headings are the only names `domain.md` has; matching them can't over-read |
| Git output read with pinned options (`-c core.quotepath=off`, `--no-renames`, `--format=`) | Default porcelain | Recurring defect: user config changes porcelain output |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** spec §B1 (scope by feature): Given a spec and an sdlc state whose `## Criteria` lists F-TSK-01.AC1 and whose `## Tasks` names `src/create.py` and a test, when `oracle.py scope REPO --oracle SPEC` runs, then F-TSK-01's part has `files: ["src/create.py"]`, its story path, its criteria with level and text, `domain_rules: ["Roles", "Identifiers"]`, `operations: ["createTask"]`, `changed_lines` 3 and `failure_modes` 2; a feature with 9 files keeps 8 and lists the 9th; a feature found only through a change file and the commit naming it gets that commit's source file; a feature with no source file is listed under `not_hunted`.
- **AC-002** spec §B1 (risk ranking): Given features at level 1 and level 2 with 16 and 3 changed lines, when scoped, then the order is the level-1 feature, then 16 lines, then 3 lines; `--max 2` keeps two and lists the third under `skipped`; `--budget 200000` keeps one.
- **AC-003** spec §B1 (Expected from the spec): Given a draft, when `drafts.py check --oracle SPEC` runs, then an Expected citing `F-TSK-01.AC2` or `domain.md §Roles`, or a draft with `Oracle: spec-gap`, passes; an unknown ID, an unknown §, or no citation fails.
- **AC-004** spec §B4 with B1: Given a verified draft, when `finding_v1.py write … --oracle SPEC` runs, then a cited criterion gives `build-defect` with `criterion` set, a cited domain rule gives `build-defect` with `rule: "domain.md §<heading>"`, and `Oracle: spec-gap` gives `spec-gap` routed to rspec; each passes `check_finding` with `verified_by.result: "reproduced"`.
- **AC-005** Given a missing spec folder, a folder without `criteria.lock.json` or an unreadable lock, when `oracle.py scope` runs, then it prints one `error:` line and exits 1, without a traceback.
- **AC-006** spec §B1: `/hunt --oracle <spec>` scopes with `oracle.py`, shows the ranking (level < 2, changed lines, failure modes) and the parts left out before the cost question, gives hunters the oracle brief and verifiers the cited criterion's text, and checks drafts and writes findings with `--oracle`; without `--oracle` nothing changes. `[manual: prompt text, checked in Review against the spec]`

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_oracle.py › test_parts_are_features_with_their_spec_and_source_files | `uv run pytest tests/test_oracle.py::test_parts_are_features_with_their_spec_and_source_files` |
| AC-002 | tests/test_oracle.py › test_ranking_puts_unproven_criteria_then_changed_lines_first | `uv run pytest tests/test_oracle.py::test_ranking_puts_unproven_criteria_then_changed_lines_first` |
| AC-003 | tests/test_oracle.py › test_expected_cites_the_spec_or_marks_a_spec_gap | `uv run pytest tests/test_oracle.py::test_expected_cites_the_spec_or_marks_a_spec_gap` |
| AC-004 | tests/test_finding_v1.py › test_oracle_expected_sets_the_class | `uv run pytest tests/test_finding_v1.py::test_oracle_expected_sets_the_class` |
| AC-005 | tests/test_oracle.py › test_a_bad_oracle_is_one_error_line | `uv run pytest tests/test_oracle.py::test_a_bad_oracle_is_one_error_line` |
| AC-006 | manual | prompt text: no test can run an agent; Review checks `commands/hunt.md`, `agents/bug-hunter.md` and `agents/repro-verifier.md` against spec §B1 |

## Must never break

- Without `--oracle`, `/hunt`, `scope.py`, `drafts.py check` and `finding_v1.py` behave exactly as on part 1.
- Nothing is written in the target repo or the spec folder; the spec is read only.

## Failure modes

- Untrusted input (lock, stories, state files and commit messages come from the hunted repo): parsed as text or JSON only, never run; git called with an argument list → AC-005
- Odd file names (spaces, non-ASCII) in Tasks lists and git output → AC-001 (the test repo path has a space and `ö`)

## Out of scope

- `--reference` and classification (part 3), browser mode (part 4), `departures.yaml` (part 5).
- A live hunt: none is run in part 2.
- A version bump or release tag: the release runbook has no pre-release step.

## Review

- **Recommended and chosen:** code, default depth (built-in `code-review`, medium), because Public Surface isn't `- none`; chosen by the trigger list (low risk, not asked). Rounds 2 and 3 ran on the orchestrator's typed decisions (msg_ea9882f3a307, msg_5846ed272ed6).
- **Verdicts:** `.sdlc/.work/findings/2026-11-08-m-oracle-scoping/code-reviewer-r1.md` FAIL, `r2.md` FAIL, `r3.md` FAIL, then `waived round 3` after its five findings were fixed, each with its own test.
- **Fixed:** r1: a § cited twice failed; prefix headings matched by substring (`rule_citations` now takes the longest heading ending at a word boundary and counts unknown citations); the lock's story path could leave the spec (`_inside`); `write --oracle` now refuses what `check --oracle` refuses; Drop criteria no longer rank a feature first; `budget.left_out` counts only the budget's cut; change files only under `<docs_dir>/changes`; `./` and `\` Tasks paths. r2: non-ASCII and multi-space headings, a space after §, `docs_dir` spellings, an empty story path. r3: tie-break on the normalised heading, more `docs_dir` spellings, a state's `Change:` path, `story` reported as read, a folder or missing story refused. Tests: `tests/test_oracle.py`, `tests/test_finding_v1.py::test_oracle_expected_sets_the_class`.
- **Tickets:** `classify_by_oracle` re-parses what `oracle_problems` parsed; `drafts.expected_body` and `finding_v1._sections` duplicate a section loop; `cited_rules` is a one-line wrapper of `rule_citations`.
- **Drift and manual checks:** Deviations: source files from sdlc 3.x state files (`## Criteria`, `## Tasks`) instead of change files' `## Tasks` (orchestrator-approved); helper exports behind the CLIs; `waived round 3`. Tests: `uv run pytest` 182 passed, 17 failed, all 17 the Windows rows in `.sdlc/baseline.md` (diffed). AC-006 (manual): `commands/hunt.md` (Spec oracle section), `agents/bug-hunter.md` (Spec oracle) and `agents/repro-verifier.md` (Cited criteria) checked against spec §B1 by review round 1; without `--oracle` their text is unchanged.
- **Lessons filed:** None.
