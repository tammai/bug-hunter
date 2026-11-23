# No credential from the origin URL reaches the drafts folder name

## Why

Request (docs/sdlc/todo.md, S1 from the security review of 2026-11-23-s-drafts-origin-error): "`drafts.py`'s origin parser stops at the first `@`, so a password with an un-escaped `@` or a query token can reach the printed drafts folder name; take the parts from `urlsplit` and pin the folder of good URLs (S1)".

Proof: `tests/test_drafts.py › test_no_credential_reaches_the_drafts_folder` gives a repo the origin `https://user:p@ss@github.com/acme/web.git`; `findings.py dir` prints a folder under `ss@github.com`, the tail of the password. A `?private_token=` or `#…` suffix lands in the last folder part the same way.

Root cause: `URL_ORIGIN`'s userinfo group `(?:[^@/]*@)?` ends at the first `@`, and the path group keeps any query and fragment.

## Decisions

- Userinfo runs to the last `@` before the path (`(?:[^/]*@)?`), the query and fragment are cut from an http(s) path (in SCP and ssh paths `?` and `#` are file-name characters), and an origin with any `@` left after the user info the pattern took (in the host or the raw path, checked before the query or fragment is cut: an `@` in an SCP password, `/`, `?` or `#` in a token) is refused; a repo with no origin keeps naming its folder from its own name, `@` included (owner's answers at the review cap: option A after round 2, option B after round 3, the raw-text check after round 4, 2026-11-23), with the usual error that never prints the URL (security review round 1, H1 and M1). Good origins keep byte-identical parts, pinned by a test, since the folder is the key for existing drafts and `posted.json`. Ruled out: rewriting the parser on `urlsplit`, a larger change to the folder identity than this needs.

## Acceptance criteria

- AC-001: no part of a user name, password, query or fragment in the origin URL appears in the drafts folder; the folder is `<host>/<path parts>`.
- AC-002: an origin whose user info can't be delimited is refused with one `error:` line that holds none of it.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_drafts.py › test_no_credential_reaches_the_drafts_folder | `uv run pytest tests/test_drafts.py -k test_no_credential_reaches_the_drafts_folder` |
| AC-002 | tests/test_drafts.py › test_an_origin_with_userinfo_it_cant_delimit_is_refused | `uv run pytest tests/test_drafts.py -k test_an_origin_with_userinfo_it_cant_delimit_is_refused` |

## Must never break

- Every origin that named a folder before names the same folder: `tests/test_drafts.py › test_drafts_folder_of_good_origins_is_unchanged` pins HTTPS, HTTPS with userinfo and port, SCP, ssh with port, `c#` and `a?b` in SCP and ssh paths, and an Azure user name (it passes before and after). An origin with an `@` in any path part, such as `https://host/acme/w@b` or `https://host/@scope/repo`, is now refused: a real path's `@` can't be told from leaked user info.

## Out of scope

- S2 (git stderr quoting a remote), still a ticket.

## Review

- **Fired and ran:** security, because risk is high (a credential reaching a printed folder name); on opus. Rounds 3–5 by the owner's `Review cap` answers (option A, option B, then one more round).
- **Verdicts:** `.sdlc/.work/findings/2026-11-23-s-drafts-origin-userinfo/security-r1.md` → FAIL — H1, M1; `security-r2.md` → FAIL — R2-H1; `security-r3.md` → FAIL — R3-H1; `security-r4.md` → FAIL — R4-H1; `security-r5.md` → PASS.
- **Fixed:** H1 (the `?`/`#` cut only for http(s); SCP and ssh paths keep them, pinned); M1, R2-H1, R3-H1, R4-H1 (one class: user info the pattern couldn't delimit landing one place further each round; closed structurally by refusing any `@` left in the host or raw path, before any cut, in `_origin_parts`), all in AC-002; R2-M1 (a no-origin repo named with `@` keeps its folder, tested).
- **Tickets:** L1 (Windows: a `\` or drive letter in a folder part can escape `~/.bug-hunter`; Windows-specific, in `docs/sdlc/todo.md`), L2 (test gaps, mostly closed by the pins). S2 from the earlier review stays a ticket.
- **Lessons filed:** one line in `docs/sdlc/recurring-defects.md` (a credential guard keyed on where a parser should have stopped).
