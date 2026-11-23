# oracle.py reads the hunted repo's history the same way on every machine

## Why

Request (docs/sdlc/todo.md, `oracle.py` tickets, R2-3): "`_git` doesn't pin `log.showRoot`, `log.diffMerges`, `diff.algorithm` or `GIT_DIR`".

Proof: `tests/test_oracle.py › test_git_reads_the_same_history_whatever_the_owners_git_setup` runs the same `log --numstat` with `GIT_DIR` pointing at another repo and `log.showRoot=false`, `diff.algorithm=patience` set through `GIT_CONFIG_*`; the output differs from a clean run, so the ranking by changed lines would rest on the owner's setup, or on another repo entirely.

Root cause: `_git` pins quoting, colour, signatures and rename following, but passes the owner's environment through, `GIT_*` variables included, and leaves the root-commit, merge-diff and diff-algorithm settings to their config.

## Decisions

- `_git` drops every `GIT_*` variable from the environment it passes (it only reads, so none is needed) and pins `log.showRoot=true`, `log.diffMerges=separate` (git's default) and `diff.algorithm=myers` with `-c`, which outranks repo and global config. Ruled out: dropping only `GIT_DIR`, since `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY` and the rest also change what is read.

## Acceptance criteria

- AC-001: the same `log --numstat` output comes back with or without `GIT_DIR` set elsewhere and `log.showRoot`/`diff.algorithm` set through `GIT_CONFIG_*`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_oracle.py › test_git_reads_the_same_history_whatever_the_owners_git_setup | `uv run pytest tests/test_oracle.py -k test_git_reads_the_same_history_whatever_the_owners_git_setup` |

## Must never break

- Every existing oracle test, the unborn-branch case included.

## Out of scope

- The other `oracle.py` tickets.

## Review

No review ran: no trigger fired.
