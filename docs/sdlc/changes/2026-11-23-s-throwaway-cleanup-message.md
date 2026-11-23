# throwaway.py keeps the refusal reason when cleanup fails

## Why

Request (docs/sdlc/todo.md, review r1 L1 of 2026-11-22-m-windows-suite): "throwaway.py: when cleaning up a refused copy fails, _main prints only "couldn't copy: <error>", so the refusal reason is lost and the partial copy left at dest isn't named. Catch the cleanup failure next to the refusal and say both."

Proof: `tests/test_throwaway.py › test_a_refusal_whose_cleanup_fails_says_both` makes the copy refuse (escaping symlinks) and the removal fail; stderr reads only `error: couldn't copy: [Errno 13] Permission denied: '<dest>'`.

Root cause: every refusal in `_make` removes the copy with `_rmtree(dest)` before returning its reason; when that raises `OSError`, the reason is never returned and `_main`'s generic `except OSError` reports the removal error instead.

## Decisions

- One helper, `_discard(dest, why)`, used by every refusal site: it removes the copy and returns the reason, or the reason plus "the partial copy at <dest> couldn't be removed: <error>". Ruled out: catching in `_main` (by then the reason is gone).

## Acceptance criteria

- AC-001: a refusal whose cleanup fails prints one `error:` line naming the refusal reason, the partial copy's path and the removal error.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_throwaway.py › test_a_refusal_whose_cleanup_fails_says_both | `uv run pytest tests/test_throwaway.py -k test_a_refusal_whose_cleanup_fails_says_both` |

## Must never break

- A refused copy is still removed when removal works, and every existing refusal message is unchanged.

## Out of scope

- Sharing `_clear_read_only` with `scratch.py`, and the Windows WinError 32 retry (separate todo items).

## Review

No review ran: no trigger fired.
