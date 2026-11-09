# bug-hunter 0.4.0-rc.2: a common-word login no longer drops every draft

## Why

**Request:** the orchestrator's brief (task_8551385d7944): "S-51: scripts/drafts.py check rejected a reproduced draft (whitespace-only title accepted, 201 vs reference 422) with "holds a login value of account member", because the target's account token value was `Bearer member` and `member` is also the role word used throughout the spec. Any draft mentioning "member" is dropped, so a real finding is silently lost. Fix: match a login value only as the credential it is […], not as a bare common word in prose; a short or dictionary-word token must not make every draft fail. Keep catching a real token leak." Version 0.4.0-rc.2 and a CHANGELOG entry; one test, test first.

**Proof:** `tests/test_drafts.py › test_login_value_that_is_a_common_word_only_counts_as_a_credential` failed first with `'holds a login value of account member: write -H "$MEMBER_AUTH" instead'`. Its draft text reconstructs the smoke draft: the original wasn't saved under `e2e/smoke`.

**Root cause:** `leaks()` used `live_proxy._secrets()`, which is built for masking responses. It splits `Bearer member` into pieces, keeps every piece of 6 or more characters (`member`), and `leaks()` matched each piece anywhere in the draft.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Fix in `drafts.leaks()` only. `live_proxy` gains `_pieces()`, and `_secrets()` gives the same output as before | Changing `_secrets()` | The proxy's masking of responses is not what S-51 is about and is pinned by its own tests |
| A piece is word-like when it is lowercase or Capitalized letters with up to 3 trailing digits and 6–15 characters long. Such a piece counts only after an auth scheme (`Bearer member`), or after any field or flag whose name contains the account's header or cookie name or a credential word (`access_token`, `--password`, `X-Auth-Token`, `"newPassword":`, `` password: `member` ``) | Matching only the full header value; a closed list of field names | A header with no scheme (`X-Api-Key: member`) would bring the false positive back; a fixed field list misses `access_token` (review round 1, H-1) |
| Every other piece (the full value `Bearer member`, `Zq8Wx7CeTk41`, mixed-case tokens, `S3cret!pass/x`, `user:pass`) still counts anywhere, in every decoded spelling, with the 6-character floor on forms as the proxy applies it | Raising the length floor; the floor on pieces | A short random token must stay caught, and its encoded forms too (round 1, L-1) |
| The field match is linear: one start per identifier, then possessive runs | A plain `[\w-]*name[\w-]*` | That was cubic on a long `authauth…` run, and drafts and echoed responses are untrusted |
| A credential word or header/cookie name counts only as a whole segment of the field name (split at `_`, `-` or a camelCase hump). Punctuation must come between field and value; plain spaces count only after a `--flag`. Schemes come from the account's own header values | Any substring; a fixed `bearer\|basic\|token` list; a fixed separator list | "Author: a member", "Bypass: member", "A basic member" were refused again, and `<password>member</password>` leaked (round 2, R2-H1 and R2-H2) |

## Acceptance criteria

- **AC-001** Given an account sent as `Authorization: Bearer member`, a draft whose prose says "member" passes the leak check. A draft holding `Authorization: Bearer member`, another account's long token on its own, the word in a credential field (`{"access_token": "member"}`, `--token=member`, `` password: `member` ``), or a short token's longer encoded form still fails.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_drafts.py › test_login_value_that_is_a_common_word_only_counts_as_a_credential | `uv run pytest tests/test_drafts.py::test_login_value_that_is_a_common_word_only_counts_as_a_credential` |

## Must never break

- Every leak `test_live_drafts_hide_host_and_credentials` and `test_leak_scan_catches_every_host_form` catch is still caught: a bare token, a cookie header and a Basic password percent-encoded twice.
- The proxy masks exactly what it masked before.

## Out of scope

- A word-like password or token written alone in prose, outside any credential context. The proxy already warns about plain-word passwords.
- A second smoke run.

## Review

- **Fired:** security, because risk is high (secret-leak check). It ran on opus with `sdlc:code-reviewer`, for 2 rounds, the cap.
- **Round 1: FAIL.**
  - H-1: a word login after a prefixed field (`access_token`, `--password`, backticks) leaked.
  - H-2: the test never reached the credential-context path.
  - L-1: a short token's encoded forms were lost.
  - M-1: mixed-case tokens were treated as words.
  - All four were fixed test first. While probing, I also found and fixed a cubic backtrack in the widened field regex.
- **Round 2: FAIL.**
  - R2-H1: prose such as "Author: a member" and "A basic member" was refused again.
  - R2-H2: `<password>member</password>` and `"password": ["member"]` leaked.
  - The brief says a round-2 high security finding is still fixed and checked. Both were fixed test first (new asserts failed, then passed) and checked by probes. Prose, leak shapes and 80k-character pathological inputs all run in under 25 ms.
  - M-2 and L-2 and the rare remaining prose refusals became tickets in `docs/sdlc/todo.md`.
- **Tests:** `uv run pytest` gives 231 passed, 17 failed and 6 skipped. The 17 failures are exactly `.sdlc/baseline.md`'s rows, diffed by name. AC-001 failed first (red recorded), then passed.
- **Lint:** the changed files are clean. `uv run ruff check .` fails only on `tests/test_departures.py:103` E501, which was already there at c2c5fc0; it is filed as a ticket.
- **Deviations:** the commit is on `2026-11-09-s-release-rc1` by hand, with no push and no `ship.py`, per the brief.
