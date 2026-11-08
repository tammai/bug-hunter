# A hunter's fresh copy works on Linux again

## Why

**Request:** the coordinator relayed (2026-11-08): fix the Linux failure CI found on `v0.3.2` test-first on a local branch, plus the corrected Deviations line; push, PR and `v0.3.3` wait for the user.

**Proof:** CI `verify (ubuntu-latest)` on `7789477` ([run 42459256915](https://github.com/tammai/bug-hunter/actions/runs/42459256915)): `tests/test_isolate.py › test_a_hunter_can_replace_its_copy_after_the_prefix` fails with `error: git clone failed: sh: 0: getcwd() failed: No such file or directory`. Since `5685cae` the isolation prefix starts each agent call inside `<scratch>/copy`, so the hunter's fresh-copy step (`rm -rf "<SCRATCH>/copy"`, then `throwaway.py`) deletes the folder its own shell sits in. The test passes on Windows, where Git Bash keeps a working folder usable after it is deleted, so the red run is CI's, not a local one.

**Root cause:** `scripts/throwaway.py` `_git` runs git in the caller's working folder. Every call names its repo with `-C` or absolute paths, but git and the `sh` it starts still need a current folder that exists.

Also: CI `invariants` ([run 42459256892](https://github.com/tammai/bug-hunter/actions/runs/42459256892)) wants a Deviations line naming the baseline row added in 0.3.2 as `tests/test_scope.py › test_live_keeps_only_parts_serving_http`; the B0 record named it with pytest's `::`.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| `_git` runs in the system temp folder, which always exists | Telling hunters to `cd "<SCRATCH>"` first | The script is what every caller runs; a prompt rule can be forgotten (B0 run 10) |

## Acceptance criteria

- **AC-001** — `throwaway.py` makes a copy when its caller's working folder has been deleted (a hunter replacing its copy from inside it).

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_isolate.py › test_a_hunter_can_replace_its_copy_after_the_prefix | `uv run pytest tests/test_isolate.py::test_a_hunter_can_replace_its_copy_after_the_prefix` |

## Must never break

- Copies are still made from the given repo only, never from the caller's folder.

## Out of scope

- Publishing: push, PR, merge and `v0.3.3` wait for the user's go-ahead.

## Review

No review ran: S, low risk, no trigger fired. AC-001's test failed on Linux CI (run 42459256915) and passes locally on Windows; Linux green is checked by this PR's CI.
