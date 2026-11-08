# B0 live validation: run bug-hunter on real repos, fix what breaks

## Why

**Request:** implement [docs/specs/rebuild-upgrade/04-bug-hunter.md](../../specs/rebuild-upgrade/04-bug-hunter.md), part 0 only (§ "B0 Live validation", ships as 0.3.x). bug-hunter has never had a live `/hunt` run; no 0.4 work starts until it has, and every defect found in bug-hunter itself is fixed test first.

The coordinator chose the targets with the user (python-markdown2, json-server, godotenv, flask's `examples/tutorial` as the live HTTP service, node-express-realworld-example-app for `/audit`, all cloned under `C:/Users/Admin/orca/workspaces/bh-b0/`). Each run is recorded in `knowledge/runs/`.

### Defect 1: `/audit --max` spends its auditors on test config, not auth code

**Proof** (found during the cost preview, before any agent ran): `python3 scripts/scope.py <realworld-app> --focus security --max 2` keeps `[Dockerfile, jest.config.ts, jest.preset.js]` and `[e2e/jest.config.ts]`; with the path `src` it keeps `src/app/models/http-exception.model.ts` and `src/app/routes/routes.ts`. `src/app/routes/auth` is never among the first two.

**Root cause:** `scope.py` `_security_relevant` is a yes/no test against one keyword list that holds both strong signals (`auth`, `session`, `token`) and weak ones (`model`, `config`, `route`, `log`). Almost every part of a web app matches a weak one (`jest.config.ts` matches `config`), so the "security parts first" sort is a no-op and `--max` falls back to folder order.

### Defect 2: `/hunt --max 1` spends its only hunter on `setup.py`

**Proof:** `python3 scripts/scope.py <python-markdown2> --max 1` keeps the part `.` = `[setup.py]` and skips `lib/markdown2.py`, the whole program. The coordinator relayed the user's call (2026-11-08) to treat this as a defect.

**Root cause:** plain `/hunt` orders parts by folder name only, so root-level build and docs tooling (`setup.py`, `noxfile.py`, `*.config.ts`, `docs/conf.py`) sorts before the code it builds and `--max` keeps it first.

### Defect 3: `author` counts as `auth`

**Proof:** the `/audit src --max 2` preview on node-express-realworld-example-app keeps `src/app/routes/article` (for `author.mapper.ts`) as an identity part and leaves out `src/app/routes/auth/token.utils.ts`.

**Root cause:** keywords match as word prefixes, so `author` matches `auth`. A prefix is still needed for `authorization`, `authGuard`, `users`, `tokens`.

### Defect 4: a pasted Python traceback ends the code block early, so a proven draft is dropped

**Proof:** `/hunt lib --max 1` on python-markdown2 (run 1): the hunter proved "`markdown2 -x toc` crashes on a document without headings", but `drafts.py check` printed `missing section: ## Expected` and `missing section: ## Root cause`, and the draft was dropped before verification. The output block holds a Python 3.11+ traceback whose caret line is `             ~~~~^^^^^^^^^^`.

**Root cause:** `drafts.py` `problems`, and `findings.py` `_parse` and `_merge_where`, flip "inside a code block" on any line that starts with ```` ``` ```` or `~~~` after stripping spaces. CommonMark opens a fence only at up to 3 spaces of indent and closes it only with the same character, at least as long, and nothing after it, so the caret line is plain text inside the block.

### Defect 5: `/audit` keeps findings whose Where lines don't point into the repo

**Proof:** `/audit src --max 2` on node-express-realworld-example-app (run 5). Finding 05 cites `C:/Users/Admin/orca/workspaces/bh-b0/…/token.utils.ts:4`, so `findings.py dedupe` didn't match it to finding 04 (`src/app/routes/auth/token.utils.ts:4`, same root cause) and both were reported. Finding 18 cites `src/main.ts:85` as the sink; the file has 57 lines (the code is at 43–44, as finding 19 cites). Its verifier noticed and still confirmed it, so 18 and 19 were not merged either.

**Root cause:** `findings.py check` only tests that Where has a `path:line`, not that it names a line in the repo. The auditor prompt says `path:line` without saying relative to `REPO`, and nothing checks the line exists.

### Defect 6: a draft carries the owner's home path (and user name)

**Proof:** `/hunt lib --max 1` rerun on python-markdown2 (run 7): draft 05's traceback reads `C:\Users\<owner>\AppData\Local\Temp\tmp.…\lib\markdown2.py`. It passed `drafts.py check`, and `/hunt` may not rewrite a hunter's output, so a draft meant for a public issue names the owner's Windows account.

**Root cause:** `drafts.py check` looks for the target's host and tokens only in live mode, and never for the owner's own paths. Agents' scratch folders sit under the real temp folder, which on Windows is inside the home folder.

### Defect 7: a hunter leaves the target's server running, so the scratch copy isn't deleted

**Proof:** `/hunt src/service.ts src/random-id.ts src/where-operators.ts --max 1` on json-server (run 8): the hunter started `node … src/bin.ts` in its copy and never stopped it. The command's `rm -rf "$SCRATCH"` then failed (`rm: cannot remove '/tmp/tmp.…/hunter-1/copy': Device or resource busy`), and the session had to find and kill the process by hand.

**Root cause:** the agent prompts tell agents to stop the stub server, but not processes they start from the target's own code, and the commands delete the scratch folder without stopping anything first. On Windows, a Git Bash `$!` is an MSYS PID (62812 for Windows PID 21856 in a check), so only Git Bash's `kill` can stop it, not `taskkill`.

**Defect 7 again (run 10):** after `e203dbf`, a hunter on json-server `src/adapters` started two servers (ports 3457, 3458) without listing them in `bg.pids`, so `reap.py` couldn't stop them; the first verifier for draft 07 couldn't bind its port and returned `CANNOT RUN`. A rule agents must remember isn't enough: the listing has to happen without them.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Rank parts by the strongest keyword they match, in three tiers kept in `stacks.json` (identity and money: `auth` … `webhook`, `middleware`; entry points: `route` … `api`; data and config: `model` … `env`), stable within a tier | Dropping weak keywords | Data and config parts still belong before plain helpers; they just come after auth |
| Same keywords, only regrouped | Adding words (`password`, `guard`) | Smallest change that fixes the ranking; no new requirement names them |
| Plain `/hunt` (and `--live`) moves a part to the end when every file in it is build or docs tooling: a name in `stacks.json` `tooling.names` (`setup.py`, `noxfile.py`, `fabfile.py`, Gulp/Grunt files, `jest.preset.js`), a `*.config.<js/ts>` file, or a file under `docs/`; stable otherwise | Ranking by file size; dropping tooling parts | Size would reorder every repo's hunt; dropping would hide code a user asked for by path. `/audit` keeps its own tiers, since config there is relevant |
| Exact words in `stacks.json` `security.not_keywords` (`author`, `authors`, `authored`, `authorship`) never match a keyword | Whole-word matching only | Would lose `authorization`, `users`, `tokens` |
| One fence reader in `drafts.py` (`fenced`, yields each line with whether it is inside a code block, CommonMark rules), used by `drafts.py` and `findings.py` (which already imports from `drafts`) | Fixing the toggle in three places | One rule, three call sites; `findings.py` already depends on `drafts.py` |
| `findings.py check --repo <repo>` fails a finding whose Where cites a path outside the repo, a missing file, or a line past the file's end; an absolute path inside the repo is accepted. `findings.py dedupe --repo <repo>` keys on the repo-relative path. `/audit` passes `--repo` to both, and the auditor prompt asks for paths relative to `REPO` | Rejecting absolute paths outright | In run 5 the article auditor wrote absolute paths throughout, including for finding 03, the most serious code finding; rejecting them would have dropped it. A wrong line can't be fixed up, and a citation that names no real line isn't evidence (constitution I) |
| `drafts.py check` fails a draft that contains the home folder of whoever runs the check (as `C:\…`, `C:/…` or Git Bash `/c/…`, any case); the hunter's output is still never rewritten, so such a draft is dropped and listed | Masking the path in place; matching the bare user name | `/hunt` never rewrites a hunter's output (constitution I); a bare name like `Admin` would reject ordinary text |
| Agents append the PID (`$!`) of every background process they start to `<SCRATCH>/bg.pids`, start the program itself rather than through a wrapper (`npm start`, `pnpm`, `go run`), and stop it before finishing. New `scripts/reap.py <scratch>` stops every PID listed in `bg.pids` at the scratch root or one level down, with `kill` (Git Bash's on Windows), accepting digits only. `/hunt` and `/audit` run it before `rm -rf "$SCRATCH"` and report a folder they couldn't remove | Finding leftovers by command line; `taskkill` | The orphan's command line was relative (`node src/bin.ts`), so it never names the scratch folder; MSYS PIDs aren't Windows PIDs |
| The isolation prefix every agent Bash call starts with (`isolate.py`'s output) also sets `trap 'jobs -p >> <scratch>/bg.pids' EXIT`, so every background job a call leaves running is listed when the call ends, whether or not the agent remembers | A `trap` that kills jobs at the end of each call | Servers must outlive the call that starts them: agents start one, then send requests from later calls |
| One change file for all of B0's fixes; each later defect adds its AC through a deviation | One feature per defect | B0 ships as one 0.3.x release with its run records |

## Acceptance criteria

- **AC-001** — 04 §B0 (fix defects test first): with `--focus security`, a part whose names match an identity keyword (`auth`, `session`, `user`, …) ranks before one matching only an entry-point keyword (`route`, `controller`, …), which ranks before one matching only a data/config keyword (`model`, `config`, …), which ranks before the rest; on a realworld-shaped repo `--max 2` keeps the `auth` parts and no jest config.
- **AC-003** — 04 §B0 (fix defects test first): without `--focus`, a part made only of build or docs tooling ranks after every other part, so `/hunt --max 1` on a repo with a root `setup.py` and `lib/` hunts `lib/`.
- **AC-004** — 04 §B0: the words `author`, `authors`, `authored`, `authorship` don't match the `auth` keyword, while `authorization` still does.
- **AC-005** — 04 §B0: `drafts.py check` and `findings.py check` read code blocks as CommonMark does: a line indented 4+ spaces, or a `~~~` line inside a backtick block, neither opens nor closes a block, so the sections after a pasted traceback still count.
- **AC-006** — 04 §B0: `findings.py check --repo <repo>` rejects a finding whose Where cites a path outside the repo, a missing file or a line past the file's end, and accepts repo-relative and absolute-inside-the-repo citations; `findings.py dedupe --repo <repo>` treats an absolute and a relative citation of the same line as the same root cause.
- **AC-007** — 04 §B0 / constitution (no person's data in output): `drafts.py check` rejects a draft containing the checking user's home folder path in Windows, forward-slash or Git Bash form, any case, and passes one without it.
- **AC-008** — 04 §B0: `reap.py <scratch>` stops every process whose PID an agent listed in `bg.pids`, ignores lines that aren't a bare number (never passing them to a shell) and PIDs that no longer exist, and exits 0 when the folder is missing.
- **AC-009** — 04 §B0: a background job started after `eval` of `isolate.py`'s output is listed in `<scratch>/bg.pids` when the shell exits, without the agent writing it, and `reap.py` then stops it.
- **AC-002** — 04 §B0 (record each run): every `/hunt` and `/audit` run in B0 has a record in `knowledge/runs/` with target and commit, cost, kept, dropped and why, and any bug-hunter defect it found.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_audit_scope.py › test_focus_ranks_identity_then_entry_points_then_data | `uv run pytest tests/test_audit_scope.py::test_focus_ranks_identity_then_entry_points_then_data` |
| AC-003 | tests/test_scope.py › test_build_and_docs_tooling_parts_come_last | `uv run pytest tests/test_scope.py::test_build_and_docs_tooling_parts_come_last` |
| AC-004 | tests/test_audit_scope.py › test_author_is_not_auth | `uv run pytest tests/test_audit_scope.py::test_author_is_not_auth` |
| AC-005 | tests/test_drafts.py › test_check_reads_fences_as_commonmark_does; tests/test_findings.py › test_check_keeps_sections_after_a_traceback_caret_line | `uv run pytest tests/test_drafts.py::test_check_reads_fences_as_commonmark_does tests/test_findings.py::test_check_keeps_sections_after_a_traceback_caret_line` |
| AC-006 | tests/test_findings.py › test_check_with_repo_needs_where_lines_that_exist; tests/test_findings.py › test_dedupe_with_repo_matches_absolute_and_relative_citations | `uv run pytest tests/test_findings.py::test_check_with_repo_needs_where_lines_that_exist tests/test_findings.py::test_dedupe_with_repo_matches_absolute_and_relative_citations` |
| AC-007 | tests/test_drafts.py › test_check_rejects_the_owners_home_path | `uv run pytest tests/test_drafts.py::test_check_rejects_the_owners_home_path` |
| AC-008 | tests/test_reap.py › test_stops_what_agents_listed_and_ignores_the_rest | `uv run pytest tests/test_reap.py::test_stops_what_agents_listed_and_ignores_the_rest` |
| AC-009 | tests/test_isolate.py › test_background_jobs_are_listed_so_reap_stops_them | `uv run pytest tests/test_isolate.py::test_background_jobs_are_listed_so_reap_stops_them` |
| AC-002 | manual | The records come from live runs that need the owner's approval and a running Claude Code session; checked by reading `knowledge/runs/` |

## Must never break

- Without `--focus security`, parts other than tooling-only ones keep folder order.
- Every security-relevant part still ranks before every non-relevant one (`test_focus_security_orders_widens_and_picks_checklists`).
- Nothing runs against a target, and no cost question is answered, without the coordinator relaying the user's approval.

## Failure modes

- Untrusted input: part and file names come from the target repo; they are only split into words and compared, never run.

## Out of scope

- B1–B6 (0.4 features).
- Publishing a release: the 0.3.x version bump and tag need a separate approval.
