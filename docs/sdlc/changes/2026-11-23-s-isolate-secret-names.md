# isolate.py drops password variables with short names

## Why

Request (docs/sdlc/todo.md, `isolate.py` review tickets from 2026-11-22-m-isolate-followups, S3 / CR1-7): "secrets in names `SECRET_NAME` misses: `PROXY_PASS`, `PROXY_PWD`, `SSHPASS`, `MYSQL_PWD`".

Proof: `tests/test_isolate.py › test_password_variables_with_short_names_are_dropped` sets those variables and runs isolation the way the agents do; `PROXY_PASS` survives into the isolated environment, where the target's code and installs can read it.

Root cause: `SECRET_NAME` matches `PASSWORD` and `PASSWD` but not the short spellings `PASS` and `PWD`.

## Decisions

- `_secret_name` keeps `SECRET_NAME` for the long spellings and adds a word rule: the name is split into words (on `_` and camelCase, trailing digits dropped), and a word that is or ends in `PASS` or `PWD` (`DBPASS`, `VPNPASS`, `DBPWD`), or is `PASSPHRASE`, `PASSCODE`, `PASSCOMMAND` or `PASSCMD`, counts, except `BYPASS`, `COMPASS`, `ASKPASS`, `OLDPWD` and similar; `PW` and `PWD` alone count only after the first word. Ruled out: a `PASS` or `PWD` substring, which would drop the shell's own `PWD` and `OLDPWD`, Playwright's `PW_*`, and harmless names such as `COMPASS_DIR`, `BYPASS_LIST` or `SSH_ASKPASS` (security review round 1, S2, asked for the whole class, not the four names).

## Acceptance criteria

- AC-001: `PROXY_PASS`, `PROXY_PWD`, `SSHPASS`, `MYSQL_PWD` and `DB_PASS_FILE` are dropped from the isolated environment; `COMPASS_DIR` and `BYPASS_LIST` are kept.
- AC-002: the name rule counts short password spellings as secrets (`GPG_PASSPHRASE`, `DB_PASS2`, `DBPASS`, `proxyPass`, `DB_PW`, `VPN_PASSCODE`, …) and not `PWD`, `OLDPWD`, `COMPASS_DIR`, `BYPASS_LIST`, `PW_TEST_HTML`, `SSH_ASKPASS` or `PASSENGER_ENV`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_isolate.py › test_password_variables_with_short_names_are_dropped | `uv run pytest tests/test_isolate.py -k test_password_variables_with_short_names_are_dropped` |
| AC-002 | tests/test_isolate.py › test_ordinary_names_are_not_secrets | `uv run pytest tests/test_isolate.py -k "test_short_password_names_count_as_secrets or test_ordinary_names_are_not_secrets"` |

## Must never break

- Every name `SECRET_NAME` dropped before is still dropped; `PWD` and `OLDPWD` keep working in the isolated shell.

## Out of scope

- The other `isolate.py` tickets (odd key or cert file names, PROXY names with `@`, `BASH_FUNC_` handling, the Windows session checks).

## Review

- **Fired and ran:** security, because risk is high (secrets reaching untrusted code); on opus.
- **Verdicts:** `.sdlc/.work/findings/2026-11-23-s-isolate-secret-names/security-r1.md` → FAIL — S1; `security-r2.md` → PASS.
- **Fixed:** S1 (the `PWD` assertion couldn't fail; PWD, OLDPWD and other kept names are now tested through `_secret_name`); S2 and R2-1 (the whole class of short password names: a word-split rule, any word ending in PASS or PWD, trailing digits dropped), in AC-002.
- **Tickets:** R2-2 (session tokens such as `OP_SESSION_<id>`, bare `*_KEY`, `*_PIN`, `PASSKEY`, `PSWD`), added to the `isolate.py` tickets in `docs/sdlc/todo.md`. Accepted: S3 and R2-3 (`ORIG_PWD`, `OldPwd` dropped; the safe side).
- **Lessons filed:** None.
