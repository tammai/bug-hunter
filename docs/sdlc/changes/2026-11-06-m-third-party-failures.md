# Hunt third-party failure handling, offline

## Why

**Request (verbatim):** "my teammate also has difficult to manage the issues on production, because it depend on other 3rd services and many factor he cant control, can we hunt these kind of bugs on a uat/prod env?" → "go ahead with approach 1 and order you propose, the approach 2 it out of scope right now" → "release then next feature, i will run by myself".

Many production bugs blamed on a third party are really the code mishandling something the service is allowed to do:
- time out or answer slowly;
- return 429 or 5xx;
- send malformed, partial or HTML bodies;
- expire a token;
- deliver a webhook twice or out of order.

`/hunt` can reproduce each one offline, with a local stub server in the throwaway copy, never touching the real service. This is approach 1 from that discussion. The prod/UAT triage tool (approach 2) stays out of scope.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| A tested, stdlib `scripts/stub_server.py` that serves scripted responses per method and path (status, headers, body, delay, dropped connection) on 127.0.0.1 and logs every request it gets | Each hunter writing its own fake server | One tested tool, and its request log is the evidence ("the client sent the charge twice", "it never retried") |
| Parts whose files call an HTTP client or a third-party SDK get the `integrations` edge-input list automatically (`scope.py`, markers in `stacks.json`) | A separate `/hunt --integrations` mode | The bugs live in the same code `/hunt` already reads; no new command to learn |
| Hunters point the code at the stub through its own configuration (a base URL in env or config, a client constructor in a small driver script). If the URL can't be changed, they use the project's own installed HTTP-mocking library (nock, msw, responses, httptest). Otherwise the suspect is "couldn't reproduce" | Intercepting DNS or the network | Stays inside the copy and the no-network rule |
| A draft's steps fetch the stub with one exact line, `curl -fsSLo stub_server.py https://raw.githubusercontent.com/tammai/bug-hunter/v<version>/scripts/stub_server.py`, pinned to the plugin's version, so maintainers can run the repro. The verifier treats that exact line as allowed and copies the local script instead of downloading | Inlining the stub in every draft | Drafts stay short and runnable, and the verifier stays offline |

## Acceptance criteria

- **AC-001** Given a scenario JSON, when `stub_server.py --scenario <file> --log <file>` runs:
  - it binds 127.0.0.1 on a free port and prints `listening on http://127.0.0.1:<port>`;
  - for each method and path it serves the scenario's responses in order, repeating the last (each response can set status, headers, body, delay seconds, or drop the connection);
  - an unmatched request gets 404 with a JSON error;
  - every request is logged as one JSON line (method, path, query, headers, body), with `Authorization`, `Cookie` and token-like headers written as `<redacted>`.
- **AC-002** Given a malformed scenario (bad JSON, missing `path`, a response that isn't an object), when `stub_server.py` starts, then it exits 1 with a one-line message and no traceback.
- **AC-003** Given parts whose files call an HTTP client or SDK (`axios`, `fetch(`, `requests.`, `httpx`, `net/http`, `reqwest`, `RestTemplate`, `Guzzle`, `Net::HTTP`, `@aws-sdk`, `stripe`, …), when `scope.py` runs, then their `edge_inputs` end with `integrations`. Other parts are unchanged. Unreadable, binary and over-1 MB files are skipped.
- **AC-004** `edge-inputs/integrations.md` covers:
  - timeouts and slow responses;
  - 429 with `Retry-After`;
  - 5xx;
  - retries that aren't idempotent;
  - malformed, partial, empty and HTML bodies;
  - expired tokens;
  - connection refused and reset;
  - duplicate and out-of-order webhooks;
  - unverified webhook signatures;
  - swallowed errors;
  - pagination ends.
- **AC-005** `agents/bug-hunter.md` tells hunters to:
  - run `stub_server.py` from `<PLUGIN>` inside the copy;
  - point code at it via its own configuration, never at the real service;
  - stop the stub before finishing;
  - write the fetch step exactly as the pinned `curl` line.

  `agents/repro-verifier.md` allows that exact line by copying `<PLUGIN>/scripts/stub_server.py` instead.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_stub_server.py › test_serves_scripted_responses_and_logs_requests | `uv run pytest tests/test_stub_server.py::test_serves_scripted_responses_and_logs_requests` |
| AC-002 | tests/test_stub_server.py › test_bad_scenarios_fail_cleanly | `uv run pytest tests/test_stub_server.py::test_bad_scenarios_fail_cleanly` |
| AC-003 | tests/test_stacks.py › test_parts_calling_third_parties_get_integrations | `uv run pytest tests/test_stacks.py::test_parts_calling_third_parties_get_integrations` |
| AC-004 | tests/test_plugin_files.py › test_integrations_list_covers_failure_modes | `uv run pytest tests/test_plugin_files.py::test_integrations_list_covers_failure_modes` |
| AC-005 | tests/test_plugin_files.py › test_agents_use_the_stub_offline | `uv run pytest tests/test_plugin_files.py::test_agents_use_the_stub_offline` |

## Must never break

- Nothing reaches a real third-party service: the stub binds 127.0.0.1 only, and agents never call the real URL.
- `scope.py`'s existing output keeps its shape (`integrations` only adds to `edge_inputs`).
- Scripts stay standard-library only.

## Out of scope

- The prod/UAT triage tool (approach 2), parked by the owner.
- Sending webhooks to a running app. Hunters call the handler directly or use the app's own test client.
- TLS on the stub, and protocols other than HTTP (gRPC, queues).
- Releasing; the runbook does that separately.
