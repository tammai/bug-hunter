# B0 live validation: run bug-hunter on real repos, fix what breaks

## Why

**Request:** implement [docs/specs/rebuild-upgrade/04-bug-hunter.md](../../specs/rebuild-upgrade/04-bug-hunter.md), part 0 only (§ "B0 Live validation", ships as 0.3.x). bug-hunter has never had a live `/hunt` run; no 0.4 work starts until it has, and every defect found in bug-hunter itself is fixed test first.

The coordinator chose the targets with the user (python-markdown2, json-server, godotenv, flask's `examples/tutorial` as the live HTTP service, node-express-realworld-example-app for `/audit`, all cloned under `<workspace>/bh-b0/`). Each run is recorded in `knowledge/runs/`.

### Defect 1: `/audit --max` spends its auditors on test config, not auth code

**Proof** (found during the cost preview, before any agent ran): `python3 scripts/scope.py <realworld-app> --focus security --max 2` keeps `[Dockerfile, jest.config.ts, jest.preset.js]` and `[e2e/jest.config.ts]`; with the path `src` it keeps `src/app/models/http-exception.model.ts` and `src/app/routes/routes.ts`. `src/app/routes/auth` is never among the first two.

**Root cause:** `scope.py` `_security_relevant` is a yes/no test against one keyword list that holds both strong signals (`auth`, `session`, `token`) and weak ones (`model`, `config`, `route`, `log`). Almost every part of a web app matches a weak one (`jest.config.ts` matches `config`), so the "security parts first" sort is a no-op and `--max` falls back to folder order.

### Defect 2: `/hunt --max 1` spends its only hunter on `setup.py`

**Proof:** `python3 scripts/scope.py <python-markdown2> --max 1` keeps the part `.` = `[setup.py]` and skips `lib/markdown2.py`, the whole program. The coordinator relayed the user's call (2026-11-08) to treat this as a defect.

**Root cause:** plain `/hunt` orders parts by folder name only, so root-level build and docs tooling (`setup.py`, `noxfile.py`, `*.config.ts`, `docs/conf.py`) sorts before the code it builds and `--max` keeps it first.

### Defect 3: `author` counts as `auth`

**Proof:** the `/audit src --max 2` preview on node-express-realworld-example-app keeps `src/app/routes/article` (for `author.mapper.ts`) as an identity part and leaves out the second `src/app/routes/auth` part.

**Root cause:** keywords match as word prefixes, so `author` matches `auth`. A prefix is still needed for `authorization`, `authGuard`, `users`, `tokens`.

### Defect 4: a pasted Python traceback ends the code block early, so a proven draft is dropped

**Proof:** `/hunt lib --max 1` on python-markdown2 (run 1): the hunter proved "`markdown2 -x toc` crashes on a document without headings", but `drafts.py check` printed `missing section: ## Expected` and `missing section: ## Root cause`, and the draft was dropped before verification. The output block holds a Python 3.11+ traceback whose caret line is `             ~~~~^^^^^^^^^^`.

**Root cause:** `drafts.py` `problems`, and `findings.py` `_parse` and `_merge_where`, flip "inside a code block" on any line that starts with ```` ``` ```` or `~~~` after stripping spaces. CommonMark opens a fence only at up to 3 spaces of indent and closes it only with the same character, at least as long, and nothing after it, so the caret line is plain text inside the block.

### Defect 5: `/audit` keeps findings whose Where lines don't point into the repo

**Proof:** `/audit src --max 2` on node-express-realworld-example-app (run 5). Finding 05 cites absolute paths (`<workspace>/…/<file>:<line>`), so `findings.py dedupe` didn't match it to finding 04 (the same root cause, cited relatively) and both were reported. Finding 18 cites `src/main.ts:85` as the sink; the file has 57 lines (the code is at 43–44, as finding 19 cites). Its verifier noticed and still confirmed it, so 18 and 19 were not merged either.

**Root cause:** `findings.py check` only tests that Where has a `path:line`, not that it names a line in the repo. The auditor prompt says `path:line` without saying relative to `REPO`, and nothing checks the line exists.

### Defect 6: a draft carries the owner's home path (and user name)

**Proof:** `/hunt lib --max 1` rerun on python-markdown2 (run 7): draft 05's traceback reads `C:\Users\<owner>\AppData\Local\Temp\tmp.…\lib\markdown2.py`. It passed `drafts.py check`, and `/hunt` may not rewrite a hunter's output, so a draft meant for a public issue names the owner's Windows account.

**Root cause:** `drafts.py check` looks for the target's host and tokens only in live mode, and never for the owner's own paths. Agents' scratch folders sit under the real temp folder, which on Windows is inside the home folder.

### Defect 7: a hunter leaves the target's server running, so the scratch copy isn't deleted

**Proof:** `/hunt src/service.ts src/random-id.ts src/where-operators.ts --max 1` on json-server (run 8): the hunter started `node … src/bin.ts` in its copy and never stopped it. The command's `rm -rf "$SCRATCH"` then failed (`rm: cannot remove '/tmp/tmp.…/hunter-1/copy': Device or resource busy`), and the session had to find and kill the process by hand.

**Root cause:** the agent prompts tell agents to stop the stub server, but not processes they start from the target's own code, and the commands delete the scratch folder without stopping anything first. On Windows, a Git Bash `$!` is an MSYS PID (62812 for Windows PID 21856 in a check), so only Git Bash's `kill` can stop it, not `taskkill`.

**Defect 7 again (run 10):** after `e203dbf`, a hunter on json-server `src/adapters` started two servers (ports 3457, 3458) without listing them in `bg.pids`, so `reap.py` couldn't stop them; the first verifier for draft 07 couldn't bind its port and returned `CANNOT RUN`. A rule agents must remember isn't enough: the listing has to happen without them.

**Root cause, from the transcript:** the hunter did list both PIDs and did `kill` them. One server was started as `printf … > db2.json && node src/bin.ts … &`, which backgrounds a subshell, so `$!` is the subshell; killing it leaves `node` running (reproduced: after `kill`, the node with a marker argument was still there; started directly with `node … &`, it ends). `reap.py` killed only the listed PID, not what runs under it. The trap from `9243852` still covers an agent that forgets to list a job.

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
| `reap.py` collects the whole process tree under each listed PID from `ps -ef` (`UID PID PPID …` on Git Bash, Linux and macOS) before stopping anything, then stops the deepest first | `kill -- -<pgid>` | Background jobs of a non-interactive shell share its process group, which can hold more than the agent's jobs |
| Review r1 H1: the isolation prefix's EXIT trap runs `reap.py <scratch> --record <jobs>`, which writes each job and the whole tree under it to `bg.pids` while the subshell still lives; agents stop their processes with `reap.py`, not `kill`, and `exec` the program after a setup command. PIDs above 2³¹−1 or longer than 10 digits are skipped (H2) | Only telling agents not to `kill` | Run 10 showed agents don't always follow such a rule; the record has to exist before anyone kills the subshell |
| Security r1: `reap.py` sets `NoDefaultCurrentDirectoryInExePath=1` and refuses a `ps`/`kill` found in the current folder (S1); `findings.py` decides "inside the repo" from the normalised text before any `resolve()` and rejects `\\`/`//` prefixes (S2); its problem lines say `Where line N, citation M` (S3) | Running `reap.py` from another folder in the commands | The script is what the commands and agents call; fixing it covers every caller |
| Defect 8 (run 3, ruled a defect by the user): a draft may claim only what its steps' output shows. The verifier lists each claimed behaviour, matches it to output, and fails the draft on an unshown one; the hunter is told to leave such claims out or draft them separately | Letting the verifier keep the draft and mark the claim | `/hunt` never rewrites a hunter's output, and a verdict line can't mark part of a draft; dropping with the claim named shows the owner what was lost |
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
- **AC-010** — 04 §B0: when a listed PID is a subshell (`( … ) &`, `cmd && prog &`), `reap.py` also stops the processes running under it.
- **AC-011** — review r1 H1: when an agent kills a listed subshell itself before `reap.py` runs, the process that ran under it is still stopped, because the isolation prefix records each background job's process tree when the call ends.
- **AC-012** — review r1 H2: a `bg.pids` line too long to be a PID (`99999999999`, 5,000 digits) is skipped, and `reap.py` exits 0 with no traceback.
- **AC-013** — security r1 S1: `reap.py` never runs a `ps` or `kill` from the current folder (the target repo's root when `/hunt` runs it), even where Windows' lookup would try it first.
- **AC-014** — security r1 S2/S3: `findings.py check --repo` never opens a cited path outside the repo (no `resolve()` on a UNC `\\host\share` or `//host/share` path), and its problem lines name a citation by its position, never by its text.
- **AC-015** — 04 §B0, coordinator ruling 3 (2026-11-08): `repro-verifier` fails a draft whose What happens or Expected states a behaviour no step's output shows (`DOES NOT REPRODUCE — unshown claim: …`), and still passes the same draft without that claim; the hunter prompt tells hunters to claim only what their steps show.
- **AC-016** — 04 §B0, constitution III: after `eval` of `isolate.py`'s output, the shell's folder is the agent's copy (`<scratch>/copy`), or the scratch folder before a copy exists, so a relative write never lands in the folder the agent started in (the target repo).
- **AC-017** — review r3 R3-1: the unshown-claim rule counts only wrong behaviours as claims; who a bug hits, a step's setup premise (an account's role) and Expected's correct behaviour and its source don't fail a draft.
- **AC-018** — 04 §B0, user ruling on run 15 (defect 10): `finding-verifier` returns `NOT CONFIRMED — wrong citation: …` when a cited line doesn't hold the code the finding quotes for it, even one line off, and still confirms the same finding with the right line.
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
| AC-010 | tests/test_reap.py › test_stops_the_processes_under_a_listed_subshell | `uv run pytest tests/test_reap.py::test_stops_the_processes_under_a_listed_subshell` |
| AC-011 | tests/test_reap.py › test_a_subshell_killed_before_reap_still_has_its_child_stopped | `uv run pytest tests/test_reap.py::test_a_subshell_killed_before_reap_still_has_its_child_stopped` |
| AC-012 | tests/test_reap.py › test_pid_lines_too_long_for_a_pid_are_skipped | `uv run pytest tests/test_reap.py::test_pid_lines_too_long_for_a_pid_are_skipped` |
| AC-013 | tests/test_reap.py › test_tools_in_the_current_folder_are_never_run | `uv run pytest tests/test_reap.py::test_tools_in_the_current_folder_are_never_run` |
| AC-014 | tests/test_findings.py › test_citations_outside_the_repo_are_never_opened_or_echoed | `uv run pytest tests/test_findings.py::test_citations_outside_the_repo_are_never_opened_or_echoed` |
| AC-015 | manual | Agent behaviour, so an eval, not a unit test: `claude -p --plugin-dir <bug-hunter>` from the godotenv clone dispatches one `repro-verifier` with `.sdlc/state/2026-11-08-m-b0-live-validation/evals/verifier-unshown-claim.md` (run 9's draft 04 plus an unshown SIGTERM claim). Before the prompt fix: `VERDICT: REPRODUCES` (red, $0.34). After: `VERDICT: DOES NOT REPRODUCE — unshown claim: a child killed by SIGTERM makes godotenv exit 1 instead of 143 (no step signals the child)` ($0.14). The same draft without the claim (`evals/verifier-honest-draft.md`): `VERDICT: REPRODUCES` ($0.31) |
| AC-016 | tests/test_isolate.py › test_relative_writes_land_in_the_copy_never_the_repo; tests/test_isolate.py › test_a_hunter_can_replace_its_copy_after_the_prefix | `uv run pytest tests/test_isolate.py::test_relative_writes_land_in_the_copy_never_the_repo tests/test_isolate.py::test_a_hunter_can_replace_its_copy_after_the_prefix` |
| AC-017 | manual | Agent behaviour, checked by eval after the fix (prompts in `.sdlc/state/2026-11-08-m-b0-live-validation/evals/`): `verifier-unshown-claim.md` → `DOES NOT REPRODUCE — unshown claim: …SIGTERM…`; `verifier-honest-draft.md` (has a "who it hits" sentence and a docs-based Expected) → `REPRODUCES`; `verifier-role-premise.md` ("a normal (non-admin) user", shown by no step) → `REPRODUCES`. About $0.30 each |
| AC-018 | manual | Agent behaviour, checked by eval (these two prompts embed a private audit finding, so they are kept in the owner's audit folder, `~/.bug-hunter/github.com/gothinkster/node-express-realworld-example-app/evals/`, not in the repo): `finding-verifier-wrong-line.md` (run 15's finding 29 as written): before the fix `VERDICT: CONFIRMED` (red, $0.36), after `VERDICT: NOT CONFIRMED — wrong citation: src/prisma/schema.prisma:44 holds id Int @id …, the quoted code email String @unique is at line 45`; `finding-verifier-right-line.md` (line 45) → `VERDICT: CONFIRMED` |
| AC-002 | manual | The records come from live runs that need the owner's approval and a running Claude Code session; checked by reading `knowledge/runs/` |

## Must never break

- Without `--focus security`, parts other than tooling-only ones keep folder order.
- Every security-relevant part still ranks before every non-relevant one (`test_focus_security_orders_widens_and_picks_checklists`).
- Nothing runs against a target, and no cost question is answered, without the coordinator relaying the user's approval.

## Failure modes

- Untrusted input: part and file names come from the target repo; they are only split into words and compared, never run.

## Out of scope

- B1–B6 (0.4 features).
- The cost preview's "about 100k tokens per hunter" matches fresh tokens but not processed tokens (3–18× with cache reads): a known issue for 0.4 (B6, `cost.jsonl`), per the user's ruling 1 (2026-11-08).
- A live hunt drops a bug the hunter can prove only offline (run 12): an observation, per ruling 2.
- Publishing a release: the 0.3.x version bump and tag need a separate approval.

## Review

**What fired:** Code at high depth (Risk high: `isolate.py`'s output is `eval`'d by every agent call and `reap.py` turns agent-written PID files into `kill` calls; new public surface `reap.py`, `check --repo`, `dedupe --repo`, `drafts.fenced`; 30+ files) and Security (Risk high). Risk was raised from low to high when the leftover-process fixes reached `isolate.py`; reviewers were approved by the coordinator (msg_274536ef2a74). Each review ran in a fresh `sdlc:code-reviewer` on opus; reports in `.sdlc/.work/findings/2026-11-08-m-b0-live-validation/`.

**Rounds and verdicts**

| Round | Code | Security | Dependency audit |
|---|---|---|---|
| 1 (whole change at `2e2f627`) | FAIL — H1, H2 | FAIL — S1, S2, S3 | PASS (`uvx pip-audit` on the locked dev deps: no known vulnerabilities) |
| 2 (fixes, `a95d551`) | PASS | PASS | — |
| 3 (defects 8–9, `069e714`, `5685cae`) | FAIL — R3-1 | PASS | — |
| 4 (R3-1, defect 10, `e5c7cdb`; past the round cap with the user's go-ahead, msg_4e10e4b4f76a) | PASS | — | — |

**High findings and what fixed them** (each test first)
- H1: an agent that killed a backgrounded subshell itself orphaned its program before `reap.py` ran → the isolation prefix's EXIT trap records each job's whole process tree (`reap.py --record`); prompts say to stop processes with `reap.py` and `exec` after a setup command (AC-011).
- H2: a `bg.pids` line too long for a PID crashed `reap.py` → PIDs bounded, `OverflowError` caught (AC-012).
- S1 (critical): on Windows, `shutil.which` searches the current folder (the target repo) first unless `NoDefaultCurrentDirectoryInExePath` is set → `reap.py` sets it and refuses a tool in the current folder (AC-013). Claude Code's own shell sets the variable, which hid the bug until the test removed it case-insensitively.
- S2: `resolve()` on an agent-cited `\\host\share` path would send the owner's NTLM credentials → containment is decided from the normalised text before any `resolve()` (AC-014).
- S3: `check --repo` echoed citation text, which can be a secret → problems are named by position (AC-014).
- R3-1 (medium bug): the unshown-claim rule contradicted the draft template ("who it hits", Expected's source) → a claim is defined as a wrong behaviour the draft says happens (AC-017, by eval).

**Tickets (not fixed here)**
- S4 / L4 / T2 (medium): a PID in `bg.pids` can be reused by an unrelated owner process before `reap.py` runs; store a start time with each PID or check the process's folder.
- Round 2 security T1/T2: a relative or repo-pointing PATH entry could still find a planted `ps`; a symlink committed in the repo pointing at a UNC share is still followed by `resolve()`.
- Round 3 security T-1: target code could swap `<scratch>/copy` for a junction so later calls `cd` into the real repo (no worse than before the fix); T-3: if both `cd`s fail the call carries on silently.
- Round 1 code L1–L3: camelCase `AuthorController.ts` still counts as `auth`; a Git Bash `/c/…` citation counts as outside the repo; a `path:line:col` citation reads as a missing file.
- Round 2 code T1: a call that ends right after `cmd && prog &` without `exec` may record only the subshell.
- Round 4 T4-1–T4-3: range citations (`:10-13`) and the wrong-citation verdict wording for described (not quoted) code; whether "who it hits" can hide an unshown platform.
- Windows 8.3 short home paths (`C:\Users\JOHNSM~1`) aren't caught by the home-path check.

**Drift:** every change from the plan is a `## Deviations` line in the state file (AC-003…AC-018 added one by one as live runs and reviews found defects; the baseline row for `test_live_keeps_only_parts_serving_http`, added with the owner's OK). Two stage-3 advances recorded a mistyped tree hash; corrections are in the state log.

**Manual checks:** AC-002 (run records 1–18 in `knowledge/runs/`, each with target and commit, cost, kept, dropped and why, defects) read by the round-1 and round-4 reviewers. AC-015, AC-017, AC-018 are agent behaviour, checked by evals whose prompts are in `.sdlc/state/2026-11-08-m-b0-live-validation/evals/` and whose verdicts are in the Acceptance tests rows.

**Lessons filed:** [knowledge/gotchas/stopping-agent-processes-on-windows.md](../../../knowledge/gotchas/stopping-agent-processes-on-windows.md); six lines added to [recurring-defects.md](../recurring-defects.md) (subshell PIDs, `cd` in a backgrounded list, Windows current-folder lookup, resolving untrusted paths, echoing rejected input, unbounded numeric fields).

**B0 exit:** runs 16, 17 and 18 (json-server `src/adapters`, flaskr live, `/audit src --max 1`) are three consecutive runs with no bug-hunter defect, after the last fix `e5c7cdb`. Ten defects were found and fixed across 18 runs; the user ruled on the borderline ones (rulings 1–3 and run 15).
