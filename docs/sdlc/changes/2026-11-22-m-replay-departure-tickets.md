# replay gives a structured failed check, and the proxy closes two gaps beside a second target

## Why

**Request (verbatim):** "Part 3 review tickets (S2-5, S2-6, S2-7, CR-12, R2-12, R2-13 from docs/sdlc/changes/2026-11-08-m-reference-classify.md Review) and Part 5 review tickets (CR-4, CR-6, CR-9, R2-10, R2-11, R2-12 from docs/sdlc/changes/2026-11-08-m-departures.md Review) as one change; a structured result from replay removes S2-7, CR-4 and R2-10. Do not edit scripts/drafts.py, oracle.py, scope.py, findings.py, isolate.py."

Running reference (`/hunt --target … --reference …`) points two proxies at two apps and classifies each finding from `finding_v1.py replay`'s results. Two review rounds left these tickets open. Three are about how a departure match works:

- `matching_departure` reads the rebuild's value back out of contracts' failure sentence (`step 1 /key: got "TSK-0003", expected …`) (CR-4).
- It decides "this is HTTP" from the steps' shape, not from the finding's runner (R2-10).
- `replay` leans on contracts' private runner and its wording, and installs a process-wide urllib opener that it never removes (S2-7).

Two are proxy gaps on untrusted input:

- A path that climbs out of the target's base path after two or more rounds of decoding passes the check (S2-5). Proven on Base: `_leaves_base("/a/%252e%252e/x")`, `"/a/..%252fx"` and `"/a/%255c..%255cx"` all return `False`, so the proxy forwards them. A target or front end that decodes twice reads `/a/../x`.
- Beside a second target, routing headers are dropped by a fixed deny-list (`ROUTING_HEADERS`). Any name it misses still reaches the front end: `X-Real-IP`, `X-Envoy-Original-Path`, or a vendor's own header.

The rest are small:

- `classify` and `write` skip a `status: proposed` departure without a word (CR-6).
- A departure ID may have any number of digits (CR-9).
- There are test and render cleanups (part 3 R2-12/R2-13, part 5 R2-11/R2-12).

**Root cause, S2-5:** `_leaves_base` (`scripts/live_proxy.py:257`) runs `unquote` once. `%25` decodes to `%`, so each extra layer of encoding hides one more `.`, `/` or `\`.

**The review reports are gone** (`.sdlc/.work/findings/2026-11-08-*` was cleared). The meaning of each ticket here is my reading of its one line in the two change files and of the code.

## Decisions

| Decision | Chosen | Ruled out | Why |
|---|---|---|---|
| Where replay's structure comes from (S2-7, CR-4) | **(a)** Keep `contracts._run_steps`. `replay` turns a failed value check into `"check": {"pointer": …, "value": …}`, once, beside the call. It reads the message's wording against the step's own checks, as `_failed_value` does today. | **(b)** Give `replay` its own step loop and opener. That reverses part 3's S-2 fix ("contracts' own runner, no copied rules") and would still need contracts' private `_pointer`, `_same` and `_rule_ok`. | `contracts/v1/` is vendored byte-identical (CONTRACTS.md Distribution, checked by `test_vendored_contracts_match_manifest`), so a public structured runner can only come from upstream. **Under (a), S2-7 stays partly open:** `replay` still calls the private `_run_steps` and `_Fail` and reads their wording, in one place now, and that half remains a ticket until contracts ships a public runner. Fixed: the global opener (below), and wording parsed outside `replay` (CR-4). |
| The structured field | An optional `check` on a `fail` result, present only when the failure is an `equals` or `rule` check, exactly one check of that step has that pointer, and the value's JSON is at most 500 characters. Otherwise there is no `check`, so no departure can match and the finding is kept. | Always present (null); a `check` index | Old drafts' Observed blocks and `browser.py`'s results stay valid. Leaving it out is the safe side: a build defect. |
| What a match still checks | `matching_departure` takes the finding's `repro` and reads `runner == "http"` (R2-10). It still requires the failing step to be the last step, the `check` pointer to be the last check's pointer, and that pointer used by only one check in the step. It never parses the message. | Trusting the result file's `check` alone | A result file is input. The rule that a check which never ran can't be hidden (part 5's CR-2) stays bound to the steps. |
| The opener (S2-7) | `replay` puts back whatever opener urllib had before, in a `finally`. | Leaving it, since the CLI is one process | `with_reference` and the tests call into the module in-process. |
| `%252e` (S2-5) | `_leaves_base` decodes until the path stops changing (at most 10 rounds; still changing after that → refused) and checks the segments after every round. | Refusing every `%25` | `%25` is an ordinary percent sign in a path (`/files/100%25`). |
| Header allow-list (S2-5): scope | Only beside a second target, where `ROUTING_HEADERS` applies today. Then the proxy forwards a request header only when its name is on the allow-list, plus the chosen account's own headers. With one target, every header passes as today. | Every hunt | With one target there is no other app to steer to, and a hunter probing the target's own headers is the job. |
| Header allow-list: contents | `accept`, `accept-language`, `authorization`, `cache-control`, `content-type`, `cookie`, `dnt`, `if-match`, `if-modified-since`, `if-none-match`, `if-range`, `if-unmodified-since`, `origin`, `pragma`, `priority`, `range`, `referer`, `upgrade-insecure-requests`, `user-agent`, `x-csrf-token`, `x-requested-with`, `x-xsrf-token`, and every `sec-` name (`sec-fetch-*`, `sec-ch-ua*`). | — | This is what crosses a pair today. contracts' replay sends `Accept` and `Content-Type`, and urllib adds `User-Agent`. A hunter's curl sends `Accept`, `Content-Type` and `User-Agent`. Playwright sends `Cookie`, `Origin`, `Referer`, `Sec-*`, CSRF headers and conditional requests. |
| Header allow-list: an unlisted header | Dropped, and the proxy log entry's note names the dropped header names. | Refusing the request (400) | Browsers add headers the hunter doesn't choose, and a refusal would break browser repros on a pair. The log shows the hunter what didn't cross. |
| CR-6 warning | `classify` and `write` print `warning: departures.yaml: <contracts' blocked line>` on stderr for each proposed entry they skip. They exit as before. | Putting it in the finding | `check_finding` validates the record's keys. `/hunt` already shows the same line before the cost question. |
| CR-9 bound | `load_departures` refuses an entry whose ID has more than 9 digits, with one `error:` line that doesn't echo the ID. It uses the same 9-digit bound as `BH-` numbers (`MAX_NUMBER`). | Leaving it to upstream contracts | The schema is vendored. An ID is quoted in the finding, its draft and the report. |
| Test cleanups (part 5 R2-11, R2-12) | Done, since this change rewrites those tests anyway: classify's departure rows move into the one table in `test_reference.py`, and the registry test is split into one test per case. | — | Free once the tests are open. |
| Render's heading scan (part 3 R2-12) | One helper finds the headings for both `render` and `_replace_section`. | — | Cheap, and `render` is touched for the new field. |

**Proposals not asked for:** none.

## Acceptance criteria

- **AC-001** — S2-5: Given a target whose base path is `/api` behind the proxy, when a request path climbs out of the base only after two or more rounds of decoding (`/%252e%252e/x`, `/%25252e%25252e/x`, `/%252E%252E/x`, `/..%252fx`, `/%255c..%255cx`), then the proxy answers 400 and the target receives no request. `/items/100%25` still reaches the target.
- **AC-002** — S2-5: Given two targets, when a client sends headers that aren't on the allow-list (`X-Real-IP`, `X-Forwarded-For`, `X-Envoy-Original-Path`, `X-Custom-Route`, and every name in `ROUTING_HEADERS`), then neither target receives them, and the proxy log entry names them. Allow-listed headers (`Accept`, `Content-Type`, `Cookie`, `Origin`, `Referer`, `User-Agent`, `X-CSRF-Token`, `Sec-Fetch-Mode`) and the account's own headers arrive. With one target, a custom header still arrives.
- **AC-003** — When `replay` runs steps whose last check fails on its value (`equals` or `rule`), it prints `{"result": "fail", "step": n, "message": …, "check": {"pointer": …, "value": …}}` with the target's value. It prints no `check` for:
  - a status mismatch;
  - a missing pointer;
  - a body that isn't JSON;
  - a pointer that two checks in the step share;
  - a value whose JSON is over 500 characters.
- **AC-004** — CR-4: `matching_departure` decides from `check` alone. A result whose message is reworded but whose `check` holds a matching value matches. A result whose message is in contracts' wording but has no `check` doesn't match.
- **AC-005** — A `check` naming a pointer other than the last check of the last step, or a step before the last, doesn't match. A result file (`--rebuild`/`--reference`) or an Observed block whose `check` isn't `{"pointer": <text>, "value": <JSON>}` is refused with one `error:` line. An old result with no `check` is still accepted.
- **AC-006** — R2-10: given a repro whose runner is not `http`, `matching_departure` returns no match even when its steps look like HTTP steps.
- **AC-007** — S2-7: after `replay` returns (pass, fail, refused or unreachable), urllib's global opener is the one that was installed before the call.
- **AC-008** — CR-6: Given a `departures.yaml` with a `status: proposed` entry, `classify` and `write` each print one `warning: departures.yaml: D-001 is proposed…` line on stderr, exit 0, and never match that entry.
- **AC-009** — CR-9: Given a `departures.yaml` entry whose ID has more than 9 digits, `classify` and `write` exit 1 with one `error:` line naming `departures.yaml`, and write no finding.
- **AC-011** — (review r1, CR-1) `finding_v1.py departures --oracle <spec>` checks the registry exactly as `write` reads it, and `/hunt` runs it before the cost question:
  - no file, or a valid one: exit 0;
  - a proposed entry: one `warning:` line, exit 0;
  - an invalid registry or an ID over 9 digits: one `error:` line, exit 1.
- **AC-010** — End to end: the reference-pair fixture is still classified as before, now through a replay result that carries `check` (`test_fixture_pair_is_classified`, with the departure draft's rebuild result taken from a real `replay` run).

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_live_proxy.py › test_a_path_that_climbs_after_repeated_decoding_is_refused | `uv run pytest tests/test_live_proxy.py -k test_a_path_that_climbs_after_repeated_decoding_is_refused` |
| AC-002 | tests/test_reference.py › test_beside_a_second_target_only_allowed_headers_cross | `uv run pytest tests/test_reference.py -k test_beside_a_second_target_only_allowed_headers_cross` |
| AC-003 | tests/test_reference.py › test_replay_reports_the_failed_check | `uv run pytest tests/test_reference.py -k test_replay_reports_the_failed_check` |
| AC-004 | tests/test_departures.py › test_departure_matches_on_the_structured_check | `uv run pytest tests/test_departures.py -k test_departure_matches_on_the_structured_check` |
| AC-005 | tests/test_departures.py › test_a_check_is_bound_to_the_last_check_and_checked | `uv run pytest tests/test_departures.py -k test_a_check_is_bound_to_the_last_check_and_checked` |
| AC-006 | tests/test_departures.py › test_departure_needs_an_http_runner | `uv run pytest tests/test_departures.py -k test_departure_needs_an_http_runner` |
| AC-007 | tests/test_reference.py › test_replay_restores_the_global_opener | `uv run pytest tests/test_reference.py -k test_replay_restores_the_global_opener` |
| AC-008 | tests/test_departures.py › test_a_proposed_entry_is_warned_about | `uv run pytest tests/test_departures.py -k test_a_proposed_entry_is_warned_about` |
| AC-009 | tests/test_departures.py › test_a_departure_id_over_nine_digits_is_refused | `uv run pytest tests/test_departures.py -k test_a_departure_id_over_nine_digits_is_refused` |
| AC-010 | tests/test_reference.py › test_fixture_pair_is_classified | `uv run pytest tests/test_reference.py -k test_fixture_pair_is_classified` |
| AC-011 | tests/test_departures.py › test_departures_command_checks_the_registry_before_the_run | `uv run pytest tests/test_departures.py -k test_departures_command_checks_the_registry_before_the_run` |

## Must never break

- A verified finding is never dropped by a departure that isn't proven. No `check`, a cut value, a non-last check, a `Defect: yes`, or a proposed or out-of-scope entry each keep the finding (part 5's CR-1, CR-2, CR-3).
- The proxy still refuses `/../x`, `/%2e%2e/x`, absolute URLs and non-ASCII paths, and one listener still reaches only its own target (`test_each_listener_reaches_only_its_own_target`, `test_forwards_only_to_the_target`).
- With one target, the proxy forwards the same headers as on Base, method overrides still refused on read-only targets.
- `replay`'s output stays ASCII, bounded (message ≤ 500 characters, with a digest when cut) and is printed as one JSON line; refused and unreachable runs stay `not run: …`.
- Every CLI failure is one `error:` line, never a traceback.
- `contracts/v1/` is not edited (vendor drift check).

## Failure modes

- **Untrusted input:**
  - request paths and header names from the hunter, and the browser it drives → AC-001, AC-002;
  - result files and Observed blocks → AC-005;
  - target-sent values in `check` → AC-003's bound, kept ASCII by `json.dumps`;
  - `departures.yaml` → AC-008, AC-009.
- **Other readers of the result shape:**
  - `result_problem`, `observed`, `load_result`, `_http_block`, `classify` and `_observed_text` in `finding_v1.py`;
  - `browser.py`'s results, which keep `{result, step, message}`;
  - the fixtures' Observed blocks;
  - `agents/bug-hunter.md`, which pastes replay's line verbatim, so it needs no change.
  - `classify`'s "same wrong" still compares step and message only.
- **Other readers of `_leaves_base`:** only `_forward` (`scripts/live_proxy.py:543`).
- Concurrency, persisted data, deploy and rollback: none. The proxy's state is unchanged, and findings gain an optional field inside the draft text only.

## Out of scope

- **S2-7, its private-runner half:** `replay` still calls contracts' `_run_steps`/`_Fail` and reads their wording. Stays a ticket until contracts ships a public structured runner (upstream).
- **S2-6:** the hunter writes its draft through a quoted heredoc. `agents/bug-hunter.md:98` already quotes it and forbids a `BH_DRAFT_END` line, and the hunter has no Write tool. Enforcing it would mean a `drafts.py` check (owned by another change) or a new tool for the hunter. Stays a ticket.
- **CR-12:** deduplicating the target-independent part of the draft leak check lives in `drafts.py.leaks`, which another change owns. Stays a ticket.
- **Part 3 R2-13:** render runs twice in reference mode. The first run is what validates the hunter's Observed block before the second replaces it, and it is cheap. Stays a ticket.
- Contracts' own departure-ID pattern (`^D-[0-9]{3,}$`): upstream.
