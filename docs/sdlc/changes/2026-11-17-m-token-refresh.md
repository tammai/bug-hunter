# Live targets mint their own tokens: a refresh command in targets.json

## Why

Request (product-rebuild, CRM S1–S4 issue list item 5e, crm-workbench `plan/drafts/product-rebuild-issues-S1-S4.md` at 1f60997): "targets.json bearer tokens last about 15 minutes, so before every hunt someone runs a scratch script to mint fresh ones. Proposed fix: a token-refresh hook, or account credentials in targets.json so the hunter can sign in itself."

The owner chose the refresh hook: `targets.json` names a command that mints the accounts' headers, the proxy runs it when it starts and again when the target answers 401. No password goes into `targets.json`, and a hunt that outlives the token keeps working instead of turning every later repro into a 401.

## Decisions

| Decision | Chosen | Ruled out, and why |
|---|---|---|
| Where the command lives | One `"refresh": ["<program>", "<arg>", …]` per target entry; it prints, on stdout, a JSON object in the same shape as `accounts` (`{"alice": {"Authorization": "Bearer …"}}`). Minted accounts replace static ones of the same name; static ones stay. | One command per account: CRM-style scripts sign in every account in one go, and per-account commands multiply the 401 handling. Printing a bare token: a cookie login or several headers wouldn't fit. |
| How it runs | An argument list, never a shell, from the folder `targets.json` is in, stdin closed, a 60 s timeout, with the caller's environment. | `shell=True` or a string command: quoting, and the scripts rule (argument lists only). |
| When it runs | At proxy start (and on `--check`), and on a 401 to a request that carried an account. At most one refresh per 30 s; concurrent 401s wait for the one running. After a refresh, the request is retried once with the new headers; if the headers didn't change (throttled, or the command failed) the 401 is passed through as is. | Refreshing on a timer: needs the token lifetime, which differs per target. Refreshing on every 401: a hunter probing auth sends many 401s on purpose, each would mint a token. |
| Budget | The retry is part of the same request: one budget slot, one log line with `"note": "retried after token refresh"` and the retry's status. | Counting the retry: the hunter can't see or control it. |
| Who runs it | Only `live_proxy.py` (proxy and `--check`). `load_target`, which `drafts.py check` and `finding_v1.py write` also call, reads and checks `refresh` but never runs it. | Running it in those checks: each would mint fresh tokens, which some identity servers rate-limit or log as a new session. |
| Masking | The masker is rebuilt after each refresh from every value minted so far plus the static ones, so a token from an earlier mint that the target echoes later is still hidden. | Masking only the newest values. |

## Acceptance criteria

- **AC-001** A target with `refresh` gets its accounts from the command when the proxy starts: a request naming a minted account reaches the target with the minted header, and static accounts of other names still work.
- **AC-002** When the target answers 401 to a request that carried an account, the proxy runs the command again and retries that request once with the new headers; the hunter gets the retry's response, one budget slot is used, and the log line has the retry's status and `"note": "retried after token refresh"`.
- **AC-003** A 401 that a refresh doesn't fix is passed through, and refreshes are at most one per 30 s: a second 401 within that window gets no new run of the command (no loop, no token storm).
- **AC-004** Minted values, from this and every earlier mint, are masked in responses and headers, and never appear in the proxy's log, stdout or stderr.
- **AC-005** At start or on `--check`, a command that can't run (missing program, non-zero exit, past 60 s, stdout not JSON, wrong shape, an account name or header that `accounts` would refuse) fails with one `error:` line naming the target and what failed, exit 1, no traceback, and none of the command's output echoed.
- **AC-006** Mid-run, a refresh that fails leaves the proxy running: the 401 is passed through, and its log line notes `token refresh failed` (never the command's output).
- **AC-007** `refresh` that isn't a non-empty list of strings fails at load with one `error:` line; `drafts.py check` and `finding_v1.py write` with `--target` load such a target without running the command.
- **AC-008** `--check` on a target with `refresh` runs it and lists the minted account names in its `target ok:` line.
- **AC-009** `commands/hunt.md` and `README.md` document the `refresh` key: its shape, when it runs, and that it runs the owner's command with the owner's environment.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_live_proxy.py › test_refresh_mints_accounts_at_start | `uv run pytest tests/test_live_proxy.py::test_refresh_mints_accounts_at_start` |
| AC-002 | tests/test_live_proxy.py › test_401_refreshes_and_retries_once | `uv run pytest tests/test_live_proxy.py::test_401_refreshes_and_retries_once` |
| AC-003 | tests/test_live_proxy.py › test_401_refreshes_and_retries_once | `uv run pytest tests/test_live_proxy.py::test_401_refreshes_and_retries_once` |
| AC-004 | tests/test_live_proxy.py › test_401_refreshes_and_retries_once | `uv run pytest tests/test_live_proxy.py::test_401_refreshes_and_retries_once` |
| AC-005 | tests/test_live_proxy.py › test_refresh_failures_are_one_line | `uv run pytest tests/test_live_proxy.py::test_refresh_failures_are_one_line` |
| AC-006 | tests/test_live_proxy.py › test_failed_refresh_mid_run_passes_401_through | `uv run pytest tests/test_live_proxy.py::test_failed_refresh_mid_run_passes_401_through` |
| AC-007 | tests/test_live_proxy.py › test_refresh_shape_checked_and_not_run_by_load | `uv run pytest tests/test_live_proxy.py::test_refresh_shape_checked_and_not_run_by_load` |
| AC-008 | tests/test_live_proxy.py › test_refresh_mints_accounts_at_start | `uv run pytest tests/test_live_proxy.py::test_refresh_mints_accounts_at_start` |
| AC-009 | manual | Prose; checked in Review against the code. |

## Must never break

- A `targets.json` without `refresh` behaves exactly as before: same accounts, same errors, same log lines.
- Tokens never reach an agent, the conversation, the log or a draft: masking covers every value the proxy has sent.
- The budget and rate limits hold: a retry never lets more requests through than `--max-requests`.
- No shell anywhere on the refresh path.

## Failure modes

- Untrusted input reaching a process: the command comes only from the owner's `targets.json`, outside the repo; nothing the target or an agent sends changes it. Its stdout is parsed as JSON and validated like `accounts`.
- Concurrent use: the proxy is threaded, so several 401s arrive together; one refresh runs, the others wait for it and retry with its result (AC-003).
- A secret in an error path: the command's stdout and stderr hold tokens or sign-in errors with passwords; errors name the target and the failure kind only (AC-005, AC-006), per recurring defect "an error line that echoes the input it rejected".

## Out of scope

- Account credentials in `targets.json` with a built-in sign-in: the hook covers it without storing passwords.
- `drafts.py check` and `finding_v1.py write` can't check drafts for minted token values (they don't run the command). The proxy's masking is what keeps tokens out of agents' sight; static values are still checked as before.
- Refreshing before expiry (reading `exp` from a JWT): the 401 path covers expiry without knowing token formats.

## Review

**What fired:** Security (Risk high: account tokens, a command run from `targets.json`) and Code (Public Surface adds a `targets.json` key; Risk high). The owner chose both.

**Round 1.** Security (`sdlc:code-reviewer`, opus): FAIL on S1–S4 and S8. Code (built-in `code-review high`), as I rated it: FAIL on the highs CR1, CR2, CR4, CR6 and CR7, plus the medium bugs CR3, CR5, CR8, CR9 and CR11. Fixed, each with a test first:
- **Token in error lines (S1/CR4):** minted accounts and headers are named by position, never by the command's text.
- **Program lookup on Windows (S2):** a bare program name is looked up on PATH only, with `NoDefaultCurrentDirectoryInExePath` set.
- **Rate and budget (S3/CR1/CR7):** the retry keeps to the rate; every line that took a budget slot carries `"forwarded": true`, and `hunt.md`'s restart and write-list rules read it.
- **Tracebacks (S4):** a deep JSON or any error in a mid-run refresh is a one-line error or `token refresh failed`; accounts are read once per request.
- **Masker race (CR2/S5):** accounts are swapped and the masker rebuilt under one lock.
- **Throttle and static accounts (CR6/CR5):** the throttle starts at the start-up mint, and a static account's 401 never mints.
- **Hang (CR8/S6):** the command's output goes to a file, not a pipe, and on timeout the process tree is killed.
- **Smaller fixes:** one Basic-password warning (CR3/S8), deduped history (CR11/S9), the same-origin check runs before minting (S10), and a concurrency test (S7).

**Round 2.** Code: PASS, with medium bugs R2-1 to R2-3 and low bugs R2-4, R2-5, R2-8, R2-11 and R2-12. Security: FAIL on two highs, N1 (a static value a mint replaced was no longer masked) and N3 (a traceback on mint I/O; `taskkill` found through PATH). The owner chose one more fix round (Review cap). Fixed, each with a test first:
- **Masking (N1):** replaced values go to history, which the masker covers; static and minted names merge case-insensitively.
- **Tracebacks (N3):** `taskkill` runs from System32, and mint I/O errors become `BadTarget`.
- **Lost accounts (R2-1):** an account a later mint leaves out keeps its token and can still trigger the next mint.
- **Planted program (R2-2/N2):** refused when found under `--repo` (as found or with links resolved) or in the current folder.
- **Error messages (R2-4/N4, R2-11):** the refusal has its own error; a folder as the program says "can't start"; the account prefix is passed in, not cut off.
- **Waiter note (N8):** throttled 401s after a failed mint carry `token refresh failed`.
- **Clean-up list (R2-8):** see round 3.

**Round 3** (the extra round). Security: PASS. One medium, M1, fixed: `hunt.md` lists writes noted `target unreachable` apart, as "may have reached the target; check", instead of dropping them. One test gap, M2, closed by `test_slow_refresh_command_is_stopped_with_its_child`, which passed on the existing code. The `_record` comment was corrected in passing.

**Tickets (not fixed here):**
- CR10: `drafts.py check` can't see minted tokens; accepted in Out of scope.
- CR13: `accounts()` rebuilds a lowercased map per call.
- R2-6: a command that exits 0 but leaves a child running is not cleaned up.
- R2-7: minted output passes through a temp file, deleted on close, rather than a pipe.
- R2-9: the masker is rebuilt while holding the shared lock.
- R2-10: the tree-kill and safe-lookup helpers are duplicated across `browser.py`, `reap.py` and `live_proxy.py`.
- L1/N6: `.cmd`/`.bat` programs run through `cmd.exe`.
- L2/N7/R2-15: the hidden `--refresh-gap` option exists for the subprocess tests.
- L3: `NoDefaultCurrentDirectoryInExePath` is left set in the proxy's environment.

**Drift (Deviations):**
- Three test-changes to `tests/test_live_proxy.py`: the header renamed to `X-Seat` because the stub redacts "session", plus the round-1 and round-2 test additions. Each was re-run red at Base.
- The 60 s timeout case was dropped from the failure matrix and later covered in-process.

**Manual:** AC-009 checked by reading. README and `hunt.md` give the `refresh` shape, when it runs (start, `--check`, 401), the throttle, that it runs as the owner, the PATH-only lookup and the drafts-check gap.

**Tests:** `uv run pytest` fails only on the 19 Windows-only tests listed in `.sdlc/baseline.md` (compared by name). Lint is clean.
