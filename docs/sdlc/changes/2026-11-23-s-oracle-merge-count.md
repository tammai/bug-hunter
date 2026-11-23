# oracle.py counts a named merge's branch commits once

## Why

Request (docs/sdlc/todo.md, `oracle.py` tickets, CR-10 of 2026-11-22-m-oracle-tickets): "a named merge and its named branch commits are counted twice".

Proof: `tests/test_oracle.py › test_a_named_merge_and_its_named_branch_commits_count_once` names a change in a branch commit that adds 3 lines and in the merge that brings it in; `oracle.py scope` reports more than 3 changed lines for the feature.

Root cause: a merge's lines are its first-parent diff, which already holds every branch commit's change, and the branch commits that name the same change are counted again.

## Decisions

- A named commit that a named merge of the same change brings in (reached from its other parents without crossing its first-parent line, worked out from the parent links the existing `git log` walk already reads, so git still runs a fixed number of times) is dropped from that change's commits: the merge counts for it. Ruled out: dropping the merge instead, which would lose the conflict resolution lines a merge can add.

## Acceptance criteria

- AC-001: a change named by a branch commit and by the merge that brings it in counts the branch's lines once.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_oracle.py › test_a_named_merge_and_its_named_branch_commits_count_once | `uv run pytest tests/test_oracle.py -k test_a_named_merge_and_its_named_branch_commits_count_once` |

## Must never break

- A merge naming a change still lists its files (`test_a_merge_commit_naming_a_change_lists_its_files`), and a history with no merges is counted as before.

## Out of scope

- The other `oracle.py` tickets (CR-9, R2-4).

## Review

No review ran: no trigger fired.
