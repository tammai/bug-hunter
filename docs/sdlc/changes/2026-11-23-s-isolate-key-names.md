# isolate.py drops key, PIN and session-token variables

## Why

Request (docs/sdlc/todo.md, `isolate.py` tickets, R2-2 of 2026-11-23-s-isolate-secret-names): "secret names still not dropped: session tokens such as `OP_SESSION_<id>`, bare `*_KEY` (`STRIPE_KEY`), `*_PIN`, `PASSKEY`, `PSWD`".

Proof: `tests/test_isolate.py › test_key_pin_and_session_names_count_as_secrets` checks those names against `_secret_name`; each reads as harmless, so isolation leaves it for the target's code and installs to read.

Root cause: `SECRET_NAME` only knows `API_KEY`, `ACCESS_KEY` and `PRIVATE_KEY`, and the word rule knows only password spellings.

## Decisions

- `KEY`, `KEYS`, `PIN`, `PINCODE`, `PAT` and `COOKIE` count after a name's first word unless a word naming where or which it is follows (`_ID`, `_FILE`, `_PATH`, `_URL`, …): `STRIPE_KEY`, `STRIPE_KEY_1`, `STRIPE_KEY_LIVE`, `SSH_KEY_B64`, `APP_KEYS`, `CARD_PIN_CODE`, `GITLAB_PAT` count; `GPG_KEY_ID`, `SSH_KEY_PATH`, `KEY_FILE_DIR`, `KEYMAP`, `PINENTRY_USER_DATA` and `MONKEY_HOME` stay. A number is its own word and never counts as the last word. `SESSION` counts as the last word (`BW_SESSION`, `AOC_SESSION`) except `DESKTOP_SESSION`, `WT_SESSION`, `KDE_FULL_SESSION`, `XRDP_SESSION` and `X2GO_SESSION`; `OP_SESSION_` names count by prefix; `XDG_SESSION_*`, `TERM_SESSION_ID` and `DBUS_SESSION_*` stay. `PASSKEY`, `PSWD`, `PSW`, `PASSW`, `PASSWRD` and `PUK` count anywhere. `COREPACK_ENABLE_AUTO_PIN` (a switch) stays. Harmless names such as `GPG_KEY` or `ORCA_PANE_KEY` are dropped: the safe side. Ruled out: any `SESSION` word, which would drop the desktop session's variables; an allowlist of variables that pass through, the structural fix (security review round 1, S6), left as a ticket since it changes what every tool sees (rounds: security review round 1 S1–S5).

## Acceptance criteria

- AC-001: the names listed in `test_key_pin_and_session_names_count_as_secrets` are secrets, and those in `test_ordinary_key_and_session_names_are_kept` are not (the Decision's examples).

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_isolate.py › test_key_pin_and_session_names_count_as_secrets | `uv run pytest tests/test_isolate.py -k "test_key_pin_and_session_names_count_as_secrets or test_ordinary_key_and_session_names_are_kept"` |

## Must never break

- Every name dropped before is still dropped, and `test_ordinary_names_are_not_secrets` still passes.

## Out of scope

- The other `isolate.py` tickets.

## Review

- **Fired and ran:** security, because risk is high (secrets reaching untrusted code); on opus.
- **Verdicts:** `.sdlc/.work/findings/2026-11-23-s-isolate-key-names/security-r1.md` → FAIL — S1, S2, S3, S4; `security-r2.md` → PASS.
- **Fixed:** S1 (a number word never counts as the last word), S2 (KEY, KEYS, PIN, PINCODE, PAT and COOKIE count after the first word unless a qualifier follows), S3 (SESSION as last word), S4 (PAT), S5 (PSW, PASSW, PASSWRD, PUK, COOKIE), F1; R2-1 (desktop session flags kept). `COREPACK_ENABLE_AUTO_PIN`, found by running the rule on a real environment's names, is kept.
- **Tickets:** S6 (pass through an allowlist instead of matching name shapes) in `docs/sdlc/todo.md`. Accepted: S7 and R2-2 (harmless names dropped: the safe side), S8 (a matched name bash can't unset stops isolation: fails closed), S9 (no-separator names), R2-3.
- **Lessons filed:** None.
