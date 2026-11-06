# Hunt a live dev server or UAT, never production

## Why

**Request (verbatim):** "can hunt the live target not source code?" → "no, i just want to hunt the local dev servers or uat env only, not prod".

`/hunt` today runs the repo's code offline in a throwaway copy, so it misses bugs that only show on a running server: real config, real data, middleware, proxies, auth. The owner wants hunters to send edge inputs to a server they are allowed to break (a local dev server or UAT) while still reading the code for the root cause, and never to reach production. It serves the owner and their teammate, who struggle with issues that appear only once deployed. The PRD's goals gain a line for it ([prd.md](../prd.md) §Goals); the Bug Bar and "Proof Before Report" stay as they are.

**The user's words** (interview, 2026-11-06):
1. How hunters know what to call: "1", code plus live URL. Hunters read routes in the code and probe the live URL; drafts keep a root cause.
2. Telling dev or UAT from production: "1 and just the url i provide". An owner-written allow-list; each run targets only the one URL the owner names.
3. Changing data: "1". Read-only unless the target allows writes; localhost allows writes; the run lists every write.
4. Logging in: "1". Named test accounts in the allow-list file, added by a local proxy; agents never see tokens.
5. Draft steps: "1". Plain `curl` with `$BASE` and `$<ACCOUNT>_AUTH` placeholders; no real host or token in a draft.
6. What `--target` hunts: "1". Only parts that serve HTTP, live; plain `/hunt` unchanged; a request budget per run.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| A mode of `/hunt`: `/hunt --target <name> [paths…] [--max N]` | A separate command; spec-only black-box probing | The owner chose code plus live URL (Q1, Q6), which is `/hunt`'s own flow with a different place to run the repro |
| A target is `http://localhost:<port>` / `http://127.0.0.1:<port>` / `http://[::1]:<port>`, or a name in `~/.bug-hunter/<host>/<owner>/<repo>/targets.json` (`{"<name>": {"url": …, "writes": bool, "accounts": {"<account>": {header: value}}}}`, next to the drafts folder). A URL that isn't localhost is refused even if it's listed: the owner names the target, never types its URL | URL on the command line with a typed confirmation; guessing production from the host name | Q2. The file sits outside the repo, so repo code can't add a target; one mistyped URL can't reach production |
| `scripts/live_proxy.py`, started by the `/hunt` command (not an agent) on 127.0.0.1, is the only way agents reach the target. It forwards to the one target base URL, adds an account's headers on `X-Bug-Hunter-Account`, refuses writes the target doesn't allow, enforces a request budget and rate, never follows redirects, and logs every request with the stub's redaction | Agents calling the target directly with rules in their prompt; one proxy per agent | One enforcement point the agents can't configure; tokens stay in the command's process; one log of every write. One proxy per run keeps it to one process |
| Writes (`POST`, `PUT`, `PATCH`, `DELETE`) only where `"writes": true`; localhost defaults to true, listed targets to false | Writes always; never writes | Q3 |
| Budget: 200 requests per agent the run dispatches, at most 5 a second, both shown at the cost question | No cap | Constitution VI (bounded cost) applied to the target's load |
| Draft steps use `"$BASE"` and `"$<ACCOUNT>_AUTH"` (e.g. `-H "$ALICE_AUTH"`), with a `Set before running:` line. The verifier sets `BASE` to the proxy and `ALICE_AUTH` to `X-Bug-Hunter-Account: alice`; a maintainer sets their own. `drafts.py check --repo <repo> --target <t>` fails a draft with the real host, a literal account header or any real account header value | Real host in the draft; the proxy in the steps | Q5: issues can be public; maintainers can't run the proxy |
| Live parts are those whose files define HTTP routes (route markers in `stacks.json`, like `integrations`); they get the `live-http` edge-input list. `scope.py --live` keeps only them and exits 1 when there are none | Every part, live and offline in one run; owner-named endpoints | Q6 |
| Constitution III gains one clause allowing live requests through the proxy to an allow-listed dev or UAT target, never production | Leaving III as is | III says target code runs only in a throwaway copy; live hunting sends requests to a running server, so the principle must say where that's allowed |

**Proposals not asked for:** none.

## Acceptance criteria

- **AC-001** Given `live_proxy.py --repo <repo> --target <t> --log <file>`:
  - `<t>` a localhost URL with a port, or a name in that repo's `targets.json` with an `http`/`https` URL → it binds 127.0.0.1 on a free port and prints `listening on http://127.0.0.1:<port>`;
  - an unlisted name, a non-localhost URL (listed or not), a missing or malformed `targets.json` for a name, or a bad field type → exit 1 with one `error:` line and no traceback.
- **AC-002** Given a running proxy, a request for `<path>?<query>` is forwarded to the target's base URL plus that path and query, and the target's status, headers and body come back unchanged. A redirect is returned as is, never followed. An absolute-form request (`GET http://other/…`) or one whose path would leave the base is refused with 400 and not forwarded.
- **AC-003** Given `X-Bug-Hunter-Account: <name>`, the account's headers are sent in its place and the selector is not forwarded. An unknown account gets 400 and isn't forwarded. No account header value appears in the proxy's log, stdout or stderr.
- **AC-004** Given a target without writes, `POST`, `PUT`, `PATCH` and `DELETE` get 403 with a JSON error and aren't forwarded. With writes allowed they're forwarded. Every forwarded request is logged as one JSON line (method, path, account name, status), with the stub's redaction for query and body.
- **AC-005** Given `--max-requests N --rate R`, request N+1 onward gets 429 from the proxy and isn't forwarded, and forwarded requests are spaced at most R a second, also under concurrent clients.
- **AC-006** Given a repo, when `scope.py <repo> --live` runs, only parts whose files define HTTP routes (Express/Fastify/Koa/Nest, Flask/FastAPI/Django, Go `net/http`/gin/echo/chi, Spring, Rails, Laravel, Sinatra, Actix/Axum) are kept, each with `live-http` last in `edge_inputs`. With none it exits 1 with a one-line message. Without `--live` the output is unchanged.
- **AC-007** Given a live draft, `drafts.py check <file> --repo <repo> --target <t>` fails it when it contains the target's host (with its port), an `X-Bug-Hunter-Account` header written out, or any of the target's account header values from `targets.json` (whole, or the part after `Bearer `/`Basic `), or when it has no `Set before running:` line naming `BASE`. A draft using `"$BASE"` and `"$<ACCOUNT>_AUTH"`, or an invented bad token, passes. Without `--target` the check is unchanged.
- **AC-008** `edge-inputs/live-http.md` covers: missing, expired and another account's credentials; another user's IDs (IDOR); missing, extra, wrong-type and null fields; malformed JSON and the wrong `Content-Type`; boundary and negative numbers; Unicode and very long strings; pagination bounds; double submits; methods a route doesn't allow; trailing slashes and case; error bodies that leak internals.
- **AC-009** `commands/hunt.md` runs `--target`: it resolves the target and refuses before any cost question when the proxy can't start; the cost question names the target (by name, never its URL), whether writes are allowed, the accounts and the request budget; it starts and stops the proxy itself; agents get the proxy URL and account names, never the target URL or tokens; the report lists every forwarded write. `agents/bug-hunter.md` and `agents/repro-verifier.md` say to send requests only to the proxy URL and to write steps with `"$BASE"`/`"$<ACCOUNT>_AUTH"`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_live_proxy.py › test_targets_resolve_or_fail_cleanly | `uv run pytest tests/test_live_proxy.py::test_targets_resolve_or_fail_cleanly` |
| AC-002 | tests/test_live_proxy.py › test_forwards_only_to_the_target | `uv run pytest tests/test_live_proxy.py::test_forwards_only_to_the_target` |
| AC-003 | tests/test_live_proxy.py › test_accounts_are_added_and_never_logged | `uv run pytest tests/test_live_proxy.py::test_accounts_are_added_and_never_logged` |
| AC-004 | tests/test_live_proxy.py › test_writes_only_where_allowed_and_logged | `uv run pytest tests/test_live_proxy.py::test_writes_only_where_allowed_and_logged` |
| AC-005 | tests/test_live_proxy.py › test_budget_and_rate | `uv run pytest tests/test_live_proxy.py::test_budget_and_rate` |
| AC-006 | tests/test_scope.py › test_live_keeps_only_parts_serving_http | `uv run pytest tests/test_scope.py::test_live_keeps_only_parts_serving_http` |
| AC-007 | tests/test_drafts.py › test_live_drafts_hide_host_and_credentials | `uv run pytest tests/test_drafts.py::test_live_drafts_hide_host_and_credentials` |
| AC-008 | tests/test_plugin_files.py › test_live_http_list_covers_edge_inputs | `uv run pytest tests/test_plugin_files.py::test_live_http_list_covers_edge_inputs` |
| AC-009 | tests/test_plugin_files.py › test_hunt_target_flow_and_agent_rules | `uv run pytest tests/test_plugin_files.py::test_hunt_target_flow_and_agent_rules` |

## Must never break

- Production is never reached: only localhost or a target the owner listed by name, and only the one target the run names.
- No token or account header value reaches an agent, a draft, the proxy's log or its output.
- Plain `/hunt` (no `--target`) behaves exactly as today: offline, no proxy.
- A target without `"writes": true` never receives a write.
- Scripts stay standard-library only.

## Failure modes

- Untrusted input: agents' requests (absolute URLs, `..` paths, huge bodies, header injection) → AC-002, AC-004; the target's responses (huge, malformed, slow) are relayed, not parsed → AC-002.
- Concurrent use: one proxy serves every agent at once; the budget and rate hold under concurrency → AC-005.
- The proxy dies mid-run: agents get connection refused, which hunters report as "couldn't reproduce", never a bug; `--idle-exit` as in the stub stops a forgotten proxy → AC-001 (start), AC-009 (lifecycle).
- Secrets: account tokens live only in `targets.json` and the proxy's process → AC-003, AC-007.

## Out of scope

- Production targets, and the parked read-only triage tool.
- `/audit --target`.
- Logging in with a username and password, OAuth flows, MFA, client TLS certificates; the owner refreshes tokens in `targets.json`.
- WebSockets, gRPC, server-sent events.
- Cleaning up data the run wrote; the report lists the writes.
- Enforcing the proxy at the OS level: agents could still open a socket to another host. Their prompts forbid it and they're never given the target URL or tokens, which is the same trust model as the offline no-network rule.
