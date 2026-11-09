# bug-hunter 0.4.0-rc.1: release prep and stdlib HTTP servers

## Why

**Request:** the orchestrator's brief (task_5b19dd22971e): bump to 0.4.0-rc.1 (plugin manifest, `bug_hunter_version`, marketplace), fold the five "Unreleased (0.4.0, part N)" CHANGELOG headings into one 0.4.0-rc.1 entry with known issues and tickets, a local tag only if the release runbook allows pre-release tags, one live `/hunt --oracle --reference` run on the fixture pair, and a push plan; push nothing.

Preparing the live run showed that `oracle.py scope --live` (and `scope.py --live`) finds no HTTP routes in a Python standard-library server (`class Handler(BaseHTTPRequestHandler)` with `do_GET`/`do_POST`), which is exactly the fixture pair, so `/hunt --target` hunts nothing there. The orchestrator (msg_666411290dd8): fix it test first on this branch, with the `BaseHTTPRequestHandler` subclass as the signal, not any `do_` method; widen the version test to accept `-rc.N`; no tag (the runbook has only `vX.Y.Z` on `main`); list the draft fetch-URL 404 as a known issue.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| One route marker in `scripts/stacks.json`: a class subclassing `BaseHTTPRequestHandler` (bare or `http.server.`-qualified) followed later in the file by a `def do_<GET\|POST\|PUT\|PATCH\|DELETE>(` | A marker for any `do_GET(` | A `do_` method alone is not a server (orchestrator) |
| No tag | `v0.4.0-rc.1` locally | `knowledge/runbooks/release.md` tags only `vX.Y.Z` on `main` at the merge commit |

## Acceptance criteria

- **AC-001** Given a repo with a stdlib server (`class Handler(BaseHTTPRequestHandler)` with `def do_GET`) and a file with a `do_GET` method on a plain class, when `scope.py --live` runs, then the server's part is kept and the plain class's part is not; every framework already recognised still is.
- **AC-002** The plugin version is `0.4.0-rc.1` in `plugin.json` and `marketplace.json`, and the version check accepts `X.Y.Z` and `X.Y.Z-rc.N`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_scope.py › test_live_route_markers_across_frameworks | `uv run pytest tests/test_scope.py::test_live_route_markers_across_frameworks` |
| AC-002 | tests/test_smoke.py › test_version_matches_manifest | `uv run pytest tests/test_smoke.py::test_version_matches_manifest` |

## Must never break

- Every route marker that matched before still matches; `scope.py` without `--live` is unchanged.
- `plugin.json` and `marketplace.json` carry the same version.

## Out of scope

- A tag, a push, a PR or a GitHub release.
- Other stdlib or framework servers not named here (`socketserver`, `wsgiref`, `aiohttp`).

## Review

- **Fired:** none. Risk is low, `## Public Surface` is `- none`, and no sensitive or UI path changed, so no review ran (S default).
- **Tests:** `uv run pytest` gives 230 passed, 17 failed and 6 skipped. The 17 failures are exactly the Windows rows in `.sdlc/baseline.md` (diffed). AC-001 and AC-002 failed first, then passed.
- **Live setup check:** `bash live-rc1.sh --setup` (no agents) now scopes both fixture features, F-TSK-01 and F-TSK-02, to `app.py` with `live-http`. Before the fix it said no feature defines HTTP routes.
- **Deviation:** committed by hand because `ship.py` is denied by the auto mode classifier here (as on parts 3 to 5).
