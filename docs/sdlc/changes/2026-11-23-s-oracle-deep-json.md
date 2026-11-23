# oracle.py refuses deeply nested spec JSON without a traceback

## Why

Request (docs/sdlc/todo.md, left from the Part 3/5 tickets, R2-6): "`oracle.py`'s `json.loads` can raise `RecursionError`".

Proof: `tests/test_oracle.py › test_deeply_nested_spec_json_is_one_error_line_or_ignored` writes 100,000 nested brackets into the spec's `openapi.json`, the hunted repo's `.sdlc/config.json` and `criteria.lock.json`; `oracle.py scope` dies with a traceback.

Root cause: the three `json.loads` calls catch `ValueError` (and the lock also `KeyError`, `TypeError`), but deep nesting raises `RecursionError`, which isn't a `ValueError`.

## Decisions

- Catch `RecursionError` beside `ValueError` at each of the three calls, as `finding_v1.py` and `live_proxy.py` already do: the lock becomes the usual one-line BadOracle error; a deep `openapi.json` gives no operations and a deep `config.json` the default docs folder, as other unreadable JSON does there.

## Acceptance criteria

- AC-001: deeply nested `openapi.json` or `config.json` is ignored like other bad JSON, and a deeply nested `criteria.lock.json` gives one `error:` line, never a traceback.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_oracle.py › test_deeply_nested_spec_json_is_one_error_line_or_ignored | `uv run pytest tests/test_oracle.py -k test_deeply_nested_spec_json_is_one_error_line_or_ignored` |

## Must never break

- Valid specs scope exactly as before.

## Out of scope

- The other replay-departure tickets.

## Review

No review ran: no trigger fired.
