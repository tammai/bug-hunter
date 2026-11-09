# Todo

## Open

- [ ] Leak check for word-like logins, review tickets left after round 2 of 2026-11-09-s-login-word (2026-11-09)
  - A word after a second word between field and value is missed: `<input name="password" value="member">`, `{"name":"token","value":"member"}`, `the password is member` (round 2, M-2).
  - A lowercase-only random token of 6–15 letters (`qwxzkvbnmt`) is treated as a word and counts only in credential context (round 2, L-2).
  - Rare prose still refused, the safe side: `Auth: member`, `a bearer member` for a Bearer account.
  - `tests/test_departures.py:103` breaks E501 (105 > 100) at c2c5fc0, so `uv run ruff check .` fails; not in `.sdlc/baseline.md`.

- [ ] `oracle.py` (part 2) review tickets, unverified, from a code review of 8dcab0e that was meant for part 3; triaged as tickets by the orchestrator (msg_34addfc88592). The `--live` and symlink findings were fixed in 2026-11-08-m-review-followups. 2026-11-08-m-review-followups (2026-11-08)
  - **Citations:**
    - `rule_citations` misses `` `domain.md` §X `` (backticked file name) and a comma between file and §;
    - `is_spec_gap` misses a bold or backticked `Oracle: spec-gap`;
    - an `Oracle: spec-gap` draft that also cites a valid criterion is classed `spec-gap`;
    - `CRITERION` doesn't match standalone `AC-nnn` IDs from an sdlc-l lock;
    - struck-through (removed) story criteria are parsed as active text.
  - **Scope:**
    - with no feature having source files, `oracle.py scope` exits 0 with zero hunters (`scope.py` exits 1);
    - `load_lock` ignores `text_sha256` drift, so an edited criterion still ranks at its locked level;
    - the verifier's "Cited criteria" use only the part's own criteria, while the check accepts any ID in the lock;
    - the commit fallback counts commits that only mention a change file, and merge commits list no files (no `-m`);
    - numstat and name-only output is parsed without `-z`, so C-quoted paths never match;
    - `_section` and `domain_headings` ignore code fences;
    - change files are linked by any `→ ID`, not only in their Acceptance criteria;
    - the non-UTF-8-name and unsafe-folder install warnings are dropped in oracle mode.
  - **Efficiency:**
    - integration markers are read for parts `--max` or `--budget` later skip;
    - one `git log` runs per feature;
    - `_commits_naming` dedupes in quadratic time;
    - `classify_by_oracle` parses the spec twice.
  - **Reuse:**
    - three section parsers (`drafts.expected_body`, `finding_v1._sections`, `oracle._section` beside `contracts._section`);
    - the max, budget and live cuts are duplicated from `scope.py`;
    - `cited_rules` is a one-line wrapper;
    - `_repo_path` duplicates `scope._relative`.
  - **Tests:** `tests/test_oracle.py` has hostile-input matrices beyond the minimal-testing rule.
- [ ] Leak scan (`drafts.leaks`) known limits and tickets, from the follow-up reviews: 2026-11-08-m-review-followups (2026-11-08)
  - a protocol-relative `//plainname` with no scheme is not counted (orchestrator: known limit, README);
  - a loopback alias on the target's port (`127.0.0.1:3999` for `localhost:3999`) refuses a finding the masker would pass (C4-1, kept by decision);
  - `localhost:80` for a portless loopback target (C4-7);
  - a host or login cut by the 500-character message cap leaves a prefix (C4-8, S-7);
  - substring matching over-refuses longer names (`xref.example.test`, `110.0.0.1`), the safe side;
  - rare spellings: expanded IPv6, punycode, a trailing-dot host;
  - `_host_patterns` and `live_proxy._masker` are two sources of truth for an address (C4-6); the masker still uses word boundaries, so the scan catches more than it masks;
  - a spec folder reached by an 8.3 short path skips the link guard; the folder links that `scope._any_matches` doesn't check (S-5);
  - escapes upper-cased after escaping (`\X2F`, `\U002F`) aren't decoded, so a plain-name host can hide behind them (R6-1);
  - other spellings of one address: expanded or zero-padded IPv6, `10.0.0.01`, `127.1`, `0.0.0.0` (R6-2);
  - a 1 MB draft mixing every encoding costs about 3 s and 97 MB to scan; bounded (R6-3).
- [ ] Part 3 review tickets, in docs/sdlc/changes/2026-11-08-m-reference-classify.md's Review: 2026-11-08-m-reference-classify (2026-11-08)
  - an allow-list of forwarded headers, and `%252e` double decoding (S2-5);
  - the hunter writes its draft through a quoted heredoc (S2-6);
  - `replay` depends on contracts' private `_run_steps`, `_Fail` and their wording, plus a process-global opener (S2-7, R2-10);
  - dedupe the target-independent draft checks (CR-12);
  - render repeats a heading scan and renders twice (R2-12, R2-13).
- [ ] Part 5 review tickets, in docs/sdlc/changes/2026-11-08-m-departures.md's Review: 2026-11-08-m-departures (2026-11-08)
  - departure matching parses contracts' failure wording; a structured value from `replay` would remove it (CR-4, with S2-7);
  - `classify` and `write` print no warning for a skipped proposed entry (CR-6);
  - registry IDs have no upper digit bound (CR-9);
  - `matching_departure` infers the runner from the steps' shape (R2-10);
  - classify's departure rows sit in two test tables, and the registry test covers several cases (R2-11, R2-12).

- [ ] Make the test suite pass on Windows: the 16 Windows-only failures in `.sdlc/baseline.md` (fake `gh` that Windows can run without passing titles through `cmd.exe`, `USERPROFILE` in the drafts and findings fixtures, POSIX-mode asserts, read-only git objects, CRLF and forbidden names in fixtures, symlink privilege), then add a `windows-latest` CI runner — left out of the Windows isolation change on purpose; 2026-11-06-m-windows-isolation (2026-11-06)
- [ ] Small `isolate.py` follow-ups from the Windows isolation review:
  - match 8.3 short names (needs `GetLongPathNameW`);
  - match a quoted value with a space inside the quotes;
  - give a one-line error instead of a traceback for an unpaired UTF-16 surrogate in a Windows env value, and fix that test's skip reason;
  - drop the extra `lstat` calls in the path fallback;
  - narrow the test guard's PATH filter so it stops hiding Homebrew's other tools on macOS.

  Review tickets (CR5, CR10, R3-1, R3-2, S4). Not bugs on the command path; 2026-11-06-m-windows-isolation (2026-11-06)
- [ ] Decide whether `isolate.py` should also unset inherited `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT` and `GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*`, which can inject git config (a credential helper) without any file — found in the Windows isolation change, not asked for there (2026-11-06)
