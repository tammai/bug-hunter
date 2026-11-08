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

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Rank parts by the strongest keyword they match, in three tiers kept in `stacks.json` (identity and money: `auth` … `webhook`, `middleware`; entry points: `route` … `api`; data and config: `model` … `env`), stable within a tier | Dropping weak keywords | Data and config parts still belong before plain helpers; they just come after auth |
| Same keywords, only regrouped | Adding words (`password`, `guard`) | Smallest change that fixes the ranking; no new requirement names them |
| Plain `/hunt` (and `--live`) moves a part to the end when every file in it is build or docs tooling: a name in `stacks.json` `tooling.names` (`setup.py`, `noxfile.py`, `fabfile.py`, Gulp/Grunt files, `jest.preset.js`), a `*.config.<js/ts>` file, or a file under `docs/`; stable otherwise | Ranking by file size; dropping tooling parts | Size would reorder every repo's hunt; dropping would hide code a user asked for by path. `/audit` keeps its own tiers, since config there is relevant |
| One change file for all of B0's fixes; each later defect adds its AC through a deviation | One feature per defect | B0 ships as one 0.3.x release with its run records |

## Acceptance criteria

- **AC-001** — 04 §B0 (fix defects test first): with `--focus security`, a part whose names match an identity keyword (`auth`, `session`, `user`, …) ranks before one matching only an entry-point keyword (`route`, `controller`, …), which ranks before one matching only a data/config keyword (`model`, `config`, …), which ranks before the rest; on a realworld-shaped repo `--max 2` keeps the `auth` parts and no jest config.
- **AC-003** — 04 §B0 (fix defects test first): without `--focus`, a part made only of build or docs tooling ranks after every other part, so `/hunt --max 1` on a repo with a root `setup.py` and `lib/` hunts `lib/`.
- **AC-002** — 04 §B0 (record each run): every `/hunt` and `/audit` run in B0 has a record in `knowledge/runs/` with target and commit, cost, kept, dropped and why, and any bug-hunter defect it found.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_audit_scope.py › test_focus_ranks_identity_then_entry_points_then_data | `uv run pytest tests/test_audit_scope.py::test_focus_ranks_identity_then_entry_points_then_data` |
| AC-003 | tests/test_scope.py › test_build_and_docs_tooling_parts_come_last | `uv run pytest tests/test_scope.py::test_build_and_docs_tooling_parts_come_last` |
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
