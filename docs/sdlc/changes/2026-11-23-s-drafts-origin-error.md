# drafts.py never prints the origin URL in its error

## Why

Request (docs/sdlc/todo.md, left from the Part 3/5 tickets, L3-3): "`drafts.py` puts an origin URL in an error".

Proof: `tests/test_drafts.py › test_a_bad_origin_error_never_prints_the_url` gives a repo the origin `https://user:<token>@github.com/acme/../web.git`; `findings.py dir` prints `error: origin URL can't name a drafts folder: <the whole URL>`, token included.

Root cause: `drafts_dir` puts the raw `git remote get-url origin` output in its `ValueError`, and an origin URL can carry a user name and token.

## Decisions

- The error names the problem, not the URL: "origin URL can't name a drafts folder: one of its path parts is empty, '.' or '..'". Ruled out: printing the URL with its userinfo stripped, which keeps a second parser of URLs to get right.

## Acceptance criteria

- AC-001: an origin URL that can't name a drafts folder gives one `error:` line that mentions the origin but none of the URL's user name or token.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_drafts.py › test_a_bad_origin_error_never_prints_the_url | `uv run pytest tests/test_drafts.py -k test_a_bad_origin_error_never_prints_the_url` |

## Must never break

- Good origin URLs give the same drafts folder as before.

## Out of scope

- The other replay-departure tickets.

## Review

- **Fired and ran:** security, because risk is high (a credential could reach an error line); on opus.
- **Verdicts:** `.sdlc/.work/findings/2026-11-23-s-drafts-origin-error/security-r1.md` → PASS.
- **Fixed:** F1 (the dots in the message are quoted).
- **Tickets:** S1 (a password with an un-escaped `@`, or a query token, in the origin URL can reach the drafts folder name, which is printed; take the folder parts from `urlsplit` and pin the folder for good URLs) and S2 (git stderr in `throwaway.py` and `oracle.py` errors could quote a remote; probe a blobless clone), added to `docs/sdlc/todo.md`.
- **Lessons filed:** None.
