# The /audit report says when a step ran without the seal

## Why

Request (docs/sdlc/todo.md, `/audit` verdict follow-ups round 2, L4): "a `recheck`, `dedupe` or `report` run without `--seal` leaves no trace in the report".

Proof: `tests/test_findings.py › test_a_report_or_recheck_run_without_the_seal_says_so` writes a report with the run's facts but no `--seal`; it reads Safe to deploy with nothing saying that an edit made during the run (to `accepted.md`, `policy.md` or a finding) wasn't ruled out.

Root cause: `--seal` is optional on `recheck`, `dedupe` and `report`, and skipping it skips the check silently.

## Decisions

- `report` run with the run's facts (`--meta`) and no `--seal` adds a note saying so; `recheck` records `"sealed": true|false` in its JSON, and the report notes a re-check that ran without it. A note, not a gap: the verdict's facts are unchanged, and `report` stays usable by hand. Ruled out: making `--seal` required, which breaks every hand run and test. `dedupe` writes no file the report reads, so it stays untraced (left in the ticket).

## Acceptance criteria

- AC-001: a report with `--meta` and no `--seal` says it ran without `--seal`; with `--seal` it doesn't; a re-check run without `--seal` records `"sealed": false` and the report says so.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_findings.py › test_a_report_or_recheck_run_without_the_seal_says_so | `uv run pytest tests/test_findings.py -k test_a_report_or_recheck_run_without_the_seal_says_so` |

## Must never break

- Every verdict reads as before; the seal check itself is unchanged.

## Out of scope

- `dedupe` without `--seal`, and the other round 2 follow-ups.

## Review

No review ran: no trigger fired.
