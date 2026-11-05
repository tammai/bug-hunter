# bug-hunter plugin v1: /hunt, the agents and /hunt-post

## Why

**Request (verbatim):** "start" → "you break down and autopilot"

Build the plugin the PRD describes ([prd.md](../prd.md), Core capabilities 1–5): one command takes a repo to a folder of ready-to-file drafts, each proven by a run repro and re-checked by a separate verifier, with the cost shown and capped before the run, known bugs skipped, and nothing posted until the owner names the drafts. The recipe that found 12 bugs in tammai/sdlc is in [BRIEF.md](../../../BRIEF.md); this packages it so it can be rerun.

**The user's words:** "you break down and autopilot": split it into parts and run them without stopping; open questions are settled by the recommendations below.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| The deterministic steps are stdlib Python scripts (`scope.py`, `known.py`, `drafts.py`, `post.py`) that the command prompts call; judgement (hunting, verifying) stays in the agents | All logic in prompts | Constitution IV: scripts can be tested, with the edge inputs we hunt for; prompts can't |
| Drafts go outside the target, in `~/.bug-hunter/<owner>-<repo>/drafts/NN.md` (folder name when there's no `origin`) | `drafts/` inside the target repo | Constitution III: nothing is left in the target. The same folder holds earlier findings, so the next run skips them |
| Parts: tracked source files (`git ls-files`), test files left out, grouped by directory into parts of at most 5 files, directories in natural order | One hunter per file; an LLM mapping step | Matches the recipe ("a few files each"), deterministic, and testable |
| Cost: 100k tokens per hunter (PRD constraint), shown with the hunter count; `/hunt` waits for the owner's go | No confirmation | Constitution VI |
| PRD open question 1: container isolation is **later**. v1 runs target code only in a throwaway copy in a temp dir, and `/hunt` asks the owner to confirm they trust the repo as part of the cost confirmation; "no" stops the run | Docker now | Smallest that meets the PRD for the first user (their own repos); recorded as out of scope |
| PRD open question 2: edge-input lists ship **generic** (the brief's list) and **python-cli** first | Go, Node and web now | The known 12 bugs are in a Python CLI (tammai/sdlc), the first target; others follow when a target needs them |
| `/hunt-post` calls `post.py`, which records what it filed in `posted.json` next to the drafts and never files a draft twice | Prompt runs `gh issue create` itself | Constitution II and the PRD's no-duplicates goal; testable |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** prd.md §Core capabilities 1: Given a git repo, when `scope.py <repo>` runs, then it prints JSON whose `parts` hold every tracked source file (paths with spaces and non-ASCII intact, test files and non-code files left out), each part at most 5 files from one directory, directories in natural order (`b2` before `b10`), with `hunters` and `est_tokens` (hunters × 100000).
- **AC-002** prd.md §Goals 4: Given more parts than `--max N`, when `scope.py <repo> --max N` runs, then `parts` holds the first N, `skipped` the rest, and `hunters`/`est_tokens` count only N; `--max 0` or a negative N exits 2 with a message.
- **AC-003** Given path arguments, when `scope.py <repo> <path>…` runs, then only files under those paths are included; a path that matches no tracked source file, or a directory that isn't a git repo, exits 1 with a one-line message and no traceback.
- **AC-004** prd.md §Core capabilities 4: When `known.py <repo> <drafts-dir>` runs, then it prints a markdown list of the repo's open issues (`gh issue list --state open`) and the titles of the drafts already in `<drafts-dir>`; when `gh` is missing or fails, or its JSON lacks keys, it still exits 0, says the open issues are unavailable and why, and lists the drafts.
- **AC-005** When `drafts.py dir <repo>` runs, then it prints `~/.bug-hunter/<owner>-<repo>/drafts` from the `origin` remote (HTTPS or SSH form), or `~/.bug-hunter/<folder name>/drafts` without one.
- **AC-006** When `drafts.py next <dir>` runs, then it prints the next free two-digit number (`01` for an empty or missing dir, `10` after `09`, `11` after `10` and `2`), ignoring files that aren't `NN.md` such as `.DS_Store` or `posted.json`.
- **AC-007** prd.md §Constraints (bug bar): When `drafts.py check <file>` runs, then it exits 0 for a draft with a `# ` title and the sections What happens · Steps to reproduce · Expected · Root cause, in that order, each non-empty, with a fenced code block in Steps to reproduce (CRLF files too); otherwise it exits 1 and names each problem.
- **AC-008** prd.md §Core capabilities 5: When `post.py <drafts-dir> <numbers>… --label <l>` runs with a logged-in `gh`, then for each named draft it runs `gh issue create --title <title> --body-file <draft> --label <l>` (an argument list, no shell), prints the URL and records it in `<drafts-dir>/posted.json`; a draft already recorded is skipped with a message and not filed again; `3` and `03` name the same draft.
- **AC-009** When any named number has no draft, a named draft fails `check`, or `gh auth status` fails, then `post.py` exits 1 before filing anything; when `gh issue create` fails part way, it stops, reports the failure, and keeps the drafts already filed in `posted.json`.
- **AC-010** prd.md §Core capabilities 2–3: `agents/bug-hunter.md` and `agents/repro-verifier.md` have `name`, `description` and `tools` frontmatter; neither has Edit, Write or NotebookEdit; both name the four draft sections; the verifier's prompt says it gets the draft alone.
- **AC-011** prd.md §Core capabilities 1: `commands/hunt.md` has `description` and `argument-hint` frontmatter and runs `scope.py`, `known.py` and `drafts.py`, dispatches `bug-hunter` and `repro-verifier`, and shows the hunter count and token cost and waits for the owner's go before the first hunter.
- **AC-012** prd.md §Core capabilities 5: `commands/hunt-post.md` has `description` and `argument-hint` frontmatter, files only through `post.py`, and never calls `gh issue create` itself.
- **AC-013** `edge-inputs/generic.md` covers each item on the brief's edge-input list and `edge-inputs/python-cli.md` exists and is non-empty.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_scope.py › test_splits_tracked_source_files_into_parts | `uv run pytest tests/test_scope.py::test_splits_tracked_source_files_into_parts` |
| AC-002 | tests/test_scope.py › test_max_caps_hunters_and_cost | `uv run pytest tests/test_scope.py::test_max_caps_hunters_and_cost` |
| AC-003 | tests/test_scope.py › test_paths_restrict_and_errors_are_clean | `uv run pytest tests/test_scope.py::test_paths_restrict_and_errors_are_clean` |
| AC-004 | tests/test_known.py › test_lists_open_issues_and_earlier_drafts | `uv run pytest tests/test_known.py::test_lists_open_issues_and_earlier_drafts` |
| AC-005 | tests/test_drafts.py › test_dir_is_outside_target_named_after_origin | `uv run pytest tests/test_drafts.py::test_dir_is_outside_target_named_after_origin` |
| AC-006 | tests/test_drafts.py › test_next_number_sorts_numerically | `uv run pytest tests/test_drafts.py::test_next_number_sorts_numerically` |
| AC-007 | tests/test_drafts.py › test_check_enforces_fixed_format | `uv run pytest tests/test_drafts.py::test_check_enforces_fixed_format` |
| AC-008 | tests/test_post.py › test_files_named_drafts_once | `uv run pytest tests/test_post.py::test_files_named_drafts_once` |
| AC-009 | tests/test_post.py › test_refuses_before_filing_and_keeps_partial_progress | `uv run pytest tests/test_post.py::test_refuses_before_filing_and_keeps_partial_progress` |
| AC-010 | tests/test_plugin_files.py › test_agents_are_read_only_and_name_draft_sections | `uv run pytest tests/test_plugin_files.py::test_agents_are_read_only_and_name_draft_sections` |
| AC-011 | tests/test_plugin_files.py › test_hunt_command_shows_cost_before_hunting | `uv run pytest tests/test_plugin_files.py::test_hunt_command_shows_cost_before_hunting` |
| AC-012 | tests/test_plugin_files.py › test_hunt_post_files_only_through_post_script | `uv run pytest tests/test_plugin_files.py::test_hunt_post_files_only_through_post_script` |
| AC-013 | tests/test_plugin_files.py › test_edge_input_lists_cover_the_brief | `uv run pytest tests/test_plugin_files.py::test_edge_input_lists_cover_the_brief` |

## Must never break

- Nothing in the scripts writes inside the target repo; `scope.py` and `known.py` only read it.
- `post.py` never files a draft the owner didn't name, and never files the same draft twice.
- Scripts use only the Python 3.12 standard library and call `git`/`gh` with argument lists, never `shell=True`.

## Failure modes

- Untrusted input (paths and draft text from the target, numbers from the owner) reaching a shell or file path → AC-001, AC-008 (argument lists; numbers resolve only to `NN.md` in the drafts dir)
- Subprocess failure (`git`, `gh` missing or failing) → AC-003, AC-004, AC-009
- Partial failure while posting → AC-009
- Edge inputs: spaces/non-ASCII paths, CRLF, empty dirs, missing JSON keys, stray files → AC-001, AC-004, AC-006, AC-007

## Out of scope

- Container isolation for untrusted repos (PRD open question 1: later).
- Edge-input lists for Go, Node and web (PRD open question 2: later).
- The PRD's success measure "a `/hunt` run on sdlc's pre-fix commit finds most of the 12 known bugs": a live run with real agents, not an automated test; the first run after merge.
- Fixing bugs; style, design or load findings (PRD non-goals).
