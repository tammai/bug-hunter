# oracle.py skips the commit-message walk when no record names a change

## Why

Request (docs/sdlc/todo.md, `oracle.py` tickets, CR-9 of 2026-11-22-m-oracle-tickets): "every commit message is read even when no record names a change".

Proof: `tests/test_oracle.py › test_commit_messages_are_not_read_when_no_record_names_a_change` builds a repo with a spec but no sdlc state or change files; `oracle.build` still runs `git log` over every commit's message, which on a large repo is the costliest call and can answer nothing.

Root cause: `build` calls `_commits_by_change` unconditionally; its result is only used for records that name a change.

## Decisions

- Walk the messages only when some record names a change; otherwise no commit can be named, so the maps are empty. Ruled out: limiting the walk with `--grep`, which still reads every message.

## Acceptance criteria

- AC-001: with no record naming a change, `build` runs no `git log` over commit messages and reports the same not-hunted features.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_oracle.py › test_commit_messages_are_not_read_when_no_record_names_a_change | `uv run pytest tests/test_oracle.py -k test_commit_messages_are_not_read_when_no_record_names_a_change` |

## Must never break

- `test_git_runs_a_fixed_number_of_times` and every other oracle test.

## Out of scope

- R2-4 (the all-history numstat walk's cost).

## Review

No review ran: no trigger fired.
