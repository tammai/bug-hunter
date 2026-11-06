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

## Review

- **Recommended and chosen:** security and code high, because `Risk: high` (test-account tokens; agents' requests reach a live server), `## Public Surface` isn't `- none`, and the track is L; chosen by the trigger list (L, self-chosen). Rounds past 2 chosen by the user ("fix, continue until no findings").
- **Verdicts** (`.sdlc/.work/findings/2026-11-06-l-live-targets/`):
  - security: r1 FAIL — S1, S2 (S3, S4 raised to high by me); r2 FAIL — S2-1; r3 PASS; r4 PASS; r5 PASS; r6 PASS.
  - code-reviewer (high): r1 FAIL — C1–C8; r2 FAIL — C2-1; r3 FAIL — C3-1; r4 PASS; r5 PASS; r6 PASS.
  - The low findings of the passing rounds (S3-1, S3-2, S4-1–S4-3, S5-1, S5-2, C3-2–C3-4, C4-1–C4-3, C5-1, C5-2) were fixed too, at the user's request; round 6 passed with no new findings.
  - Dependency audit: none ran. The plugin ships no dependencies (`dependencies = []`) and `pip-audit` isn't installed here.
- **Fixed** (each with a failing test first, in `tests/test_live_proxy.py` unless named):
  - S1, C5: account header values with line breaks or non-Latin-1 characters leaked the token in a traceback → validated at start without echoing (`test_bad_targets_fail_without_echoing_secrets`).
  - S3, C4, S2-1: responses echoing a token or the target URL reached agents → every derived form of each account value masked exactly, the target's address swapped for the proxy's, compressed bodies refused (`test_responses_keep_target_headers_and_hide_tokens_and_url`, `test_masks_every_form_of_an_account_value`, `test_masking_is_exact_and_covers_more_logins`, `test_masking_round_five_forms`, `test_compressed_bodies_refused_without_echo_but_bodiless_replies_pass`).
  - S4: method overrides on read-only targets → 403 (`test_odd_paths_overrides_and_query_dots`).
  - C1: live repro placeholders unset by isolation or unseen as prefixes → exported after the isolation step (`tests/test_plugin_files.py::test_live_steps_export_placeholders_and_keep_the_proxy_up`).
  - C2: the proxy's own Server and Date headers, HEAD lengths → only the target's headers (`test_responses_keep_target_headers_and_hide_tokens_and_url`).
  - C3: chi missed, axios instances kept → markers fixed, 11 frameworks tested (`tests/test_scope.py::test_live_route_markers_across_frameworks`).
  - C2-1, C3-1 (from fixes): host and word-password masking mangled ordinary text → bounded host matching, exact secret matching (`test_masks_hosts_only_where_they_stand_alone`, `test_masking_is_exact_and_covers_more_logins`).
  - Medium bugs S2, C6, C7, C8, low S5 and C14 fixed the same way.
- **Tickets:**
  - C9: hunters and verifiers share one request budget; hunters can use it all.
  - C10: for Rails and Laravel only the routes file is a live part, not the controllers.
  - C11: a malformed `targets.json` shows Python's raw JSON parser message.
  - C12: a draft that names the proxy URL passes the draft check.
  - C13: HTTPS targets behind an internal CA get 502 on every request, and nothing probes the target before the cost question.
  - S2-4, C2-4: a restarted proxy's remaining budget doesn't count logged 502s, so a run can exceed the approved budget by one request per 502.
  - S2-5: the status line's reason phrase is relayed unmasked.
  - C2-2: the chi marker also matches Go clients with relative paths (resty's `.R().Get("/x")`).
  - S5-1 remainder: a value mixing `&amp;` with numeric entities, and Go's JS-string escapes, aren't masked.
  - A token the target itself re-cases, base64s or encrypts isn't masked; agents never hold tokens, so masking is the second line.
- **Drift and manual checks:** the state file's Deviations: AC-007 refined before the red step (real account values, not every literal header); two plugin-file tests updated for `live-http` and constitution 1.2.0; `load_target` shared with `drafts.py`; AC-002's exception (responses masked, no proxy headers added); `--check` and the `/hunt` proxy lifecycle; rounds 3–6 masking rules. No `manual` ACs.
- **Security:** no critical or high finding open; no secrets in the diff (tests use invented tokens). Constitution principle III amended to v1.2.0 for live hunts.
- **Lessons filed:** [knowledge/gotchas/redacting-logged-requests.md](../../../knowledge/gotchas/redacting-logged-requests.md) (masking what a live target echoes); six lines in [recurring-defects.md](../recurring-defects.md); `.claude/rules/plugin-prompts.md` names the live-target exception.
