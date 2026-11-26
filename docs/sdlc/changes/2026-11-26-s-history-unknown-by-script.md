# /audit carries "git couldn't say" from the scan to the report by script

## Why

Request (docs/sdlc/todo.md, `/audit` verdict follow-ups round 2, R3-L4 and M-2): "`history_unknown` reaches the report only because `/audit` copies it into `meta.json`; carry it by script".

Today the agent running `/audit` reads `$RUN/secrets.json` and writes each `"history_unknown": true` path into `meta.json`. If it skips or gets that wrong, a local secret that git history may hold drops out of the coverage gaps, and the report can read Safe to deploy.

## Decisions

- `from-secrets-scan` writes the paths into `<out>/history_unknown.json`; `recheck --found` carries them into `recheck.json` as `history_unknown`, or `null` when the secrets scan ran but the file is missing or unreadable; the report makes each path a gap, and `null` a gap of its own. `meta.json`'s `history_unknown` is gone, and `/audit` no longer writes it. Ruled out: `report --secrets`, which is one more flag the agent could leave out.
- A hand-written `recheck.json` without the key reads as before (no gap): every recheck run writes it.

## Acceptance criteria

- AC-001: a local secret git couldn't answer for is a coverage gap in the report through `from-secrets-scan`, `recheck` and `report`, with no `history_unknown` in `meta.json`.
- AC-002: a re-check whose scanned `found` folder has no `history_unknown.json` records `null`, and the report names it as a gap; an empty list reads Safe to deploy.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_audit_scope.py › test_an_unknown_history_for_a_local_secret_is_a_gap | `uv run pytest tests/test_audit_scope.py -k test_an_unknown_history_for_a_local_secret_is_a_gap` |
| AC-002 | tests/test_findings.py › test_a_recheck_whose_scan_didnt_say_what_git_could_see_is_a_gap | `uv run pytest tests/test_findings.py -k test_a_recheck_whose_scan_didnt_say_what_git_could_see_is_a_gap` |

## Must never break

- Paths are escaped in the report and a path holding a secret is withheld; every other verdict reads as before.

## Out of scope

- The other round 2 follow-ups.

## Review

No review ran: no trigger fired.
