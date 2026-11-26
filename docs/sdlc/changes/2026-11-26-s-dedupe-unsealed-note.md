# The /audit report says when dedupe ran without the seal

## Why

Request (docs/sdlc/todo.md, `/audit` verdict follow-ups round 2, L4): "a `dedupe` run without `--seal` leaves no trace in the report (`recheck` and `report` done in 2026-11-23-s-report-unsealed-note)".

Proof: `tests/test_findings.py › test_a_dedupe_run_without_the_seal_says_so_in_the_report` runs `dedupe` without `--seal`; nothing it writes reaches the report, which reads as if every step was sealed.

Root cause: `dedupe` reads `accepted.md` (the `rotated` lines that pair a pre-id secret) and writes into the audit folder, but writes no file the report reads, so whether its seal check ran is lost.

## Decisions

- `dedupe` takes an optional `--out <json>` and writes `{"sealed": true|false, "dropped": [...]}` there, as `recheck` does; `report` takes `--dedupe <that file>` and adds a note when it says `"sealed": false`. `commands/audit.md` passes both. A note, not a gap: the verdict's facts are unchanged, as for `recheck` and `report`. Ruled out: a marker in `$AUDIT` (it would outlive the run) and a `meta.json` field (the agent writes that, not the script).

## Acceptance criteria

- AC-001: a `dedupe` run without `--seal` records `"sealed": false` in its `--out` JSON and a report given it with `--dedupe` says dedupe ran without `--seal`; a sealed `dedupe` records `"sealed": true` and the report has no such note.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_findings.py › test_a_dedupe_run_without_the_seal_says_so_in_the_report | `uv run pytest tests/test_findings.py -k test_a_dedupe_run_without_the_seal_says_so_in_the_report` |

## Must never break

- Every verdict reads as before; `dedupe` and `report` without the new flags behave as before; the seal check itself is unchanged.

## Out of scope

- The other round 2 follow-ups (SEC-3, single-branch clones, L-B, test gaps).

## Review

No review ran: no trigger fired.
