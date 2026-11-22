# Todo

## Open

- [x] `scratch.py clean` on Windows can't remove a read-only folder: `tests/test_scratch.py::test_clean_reports_size_and_removes_read_only_trees` fails with "Access is denied" on `hunter-1/home/go/pkg/mod/example.com@v1` (Go makes its module cache read-only), on `main` (v0.5.0) too, so a hunt's run folder on Windows is left partly behind. Its own S fix; baselined in 2026-11-09-m-scratch-tickets (2026-11-11). Done in 2026-11-12-m-windows-seal-and-clean; passes on Windows (2026-11-12)

- [ ] Leak check for word-like logins, review tickets left after round 2 of 2026-11-09-s-login-word (2026-11-09)
  - A word after a second word between field and value is missed: `<input name="password" value="member">`, `{"name":"token","value":"member"}`, `the password is member` (round 2, M-2).
  - A lowercase-only random token of 6–15 letters (`qwxzkvbnmt`) is treated as a word and counts only in credential context (round 2, L-2).

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
- [ ] Leak scan (`drafts.leaks`) known limits and tickets, from the follow-up reviews: 2026-11-08-m-review-followups (2026-11-08)
  - `localhost:80` for a portless loopback target (C4-7);
  - a host or login cut by the 500-character message cap leaves a prefix (C4-8, S-7);
  - a trailing-dot host;
  - `_host_patterns` and `live_proxy._masker` are two sources of truth for an address (C4-6); the masker still uses word boundaries, so the scan catches more than it masks;
  - a spec folder reached by an 8.3 short path skips the link guard; the folder links that `scope._any_matches` doesn't check (S-5);
  - escapes upper-cased after escaping (`\X2F`, `\U002F`) aren't decoded, so a plain-name host can hide behind them (R6-1);
  - other spellings of one address: expanded or zero-padded IPv6, `10.0.0.01`, `127.1`, `0.0.0.0` (R6-2);
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

- [ ] Make the test suite pass on Windows: the 19 Windows-only failures in `.sdlc/baseline.md` (fake `gh` that Windows can run without passing titles through `cmd.exe`, `USERPROFILE` in the drafts and findings fixtures, POSIX-mode asserts, read-only git objects, CRLF and forbidden names in fixtures, symlink privilege), then add a `windows-latest` CI runner — left out of the Windows isolation change on purpose; 2026-11-06-m-windows-isolation (2026-11-06)
- [ ] Small `isolate.py` follow-ups from the Windows isolation review:
  - match 8.3 short names (needs `GetLongPathNameW`);
  - match a quoted value with a space inside the quotes;
  - give a one-line error instead of a traceback for an unpaired UTF-16 surrogate in a Windows env value, and fix that test's skip reason;
  - drop the extra `lstat` calls in the path fallback;
  - narrow the test guard's PATH filter so it stops hiding Homebrew's other tools on macOS.

  Review tickets (CR5, CR10, R3-1, R3-2, S4). Not bugs on the command path; 2026-11-06-m-windows-isolation (2026-11-06)
- [x] Decide whether `isolate.py` should also unset inherited `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT` and `GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*`, which can inject git config (a credential helper) without any file — found in the Windows isolation change, not asked for there (2026-11-06). Done in 2026-11-22-s-git-config-env (2026-11-22)
- [ ] `isolate.py` passes every other inherited `GIT_*` override through: `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `SSH_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_EXEC_PATH`, `GIT_TEMPLATE_DIR`, `GIT_EXTERNAL_DIFF`, `GIT_PAGER`/`GIT_EDITOR`, `GIT_CONFIG`/`GIT_CONFIG_SYSTEM`, and `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` (caught only when they point into the home; a `GIT_DIR` at the target would let a hunter edit it). Structural fix: unset every inherited `GIT_*` except an allowlist (`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, `GIT_TERMINAL_PROMPT`, `GIT_SSL_CAINFO`). Security review S1 of 2026-11-22-s-git-config-env (2026-11-22)
- [x] Live-target tokens in `targets.json` expire mid-workflow: the CRM rebuild's bearer tokens last ~15 minutes, so someone ran a scratch script before every `/hunt` to mint fresh ones. Options: a token-refresh hook (a command `targets.json` names, run before the hunt and on a 401), or account credentials in `targets.json` so the hunter signs in itself (weigh against the secrets rules in `.claude/rules/sdlc-sensitive.md`). Raised by product-rebuild, CRM S1–S4 issue list item 5e (crm-workbench `plan/drafts/product-rebuild-issues-S1-S4.md`, commit 1f60997); evidence from crm-rebuild-sdlc-23 (2026-11-17). Done in 2026-11-17-m-token-refresh with the refresh command (2026-11-17)
- [ ] Improve how well `/hunt` finds bugs, in this order (planned to start the week of 2026-11-23); from the 19 B0 runs in `knowledge/runs/`, which measured only that kept drafts reproduce, not missed bugs or maintainer acceptance (2026-11-20)
  1. **Scoring benchmark:** 2–3 pinned repos per stack, about 10 planted bugs each with no hints in comments; score how many it finds, how many kept drafts are wrong, how often the verifier passes a bad draft, and cost per real bug. Run before and after each change.
  2. **Stricter verifier:** a checklist (every claim shown in its output, every cited line holds the quoted code), a script that checks line contents rather than just that the line exists, and bad drafts planted in the benchmark (defects 5, 8 and 10).
  3. **More bugs per run:** two hunters with different focus per part (input edge cases vs state and error paths), checking whether recent fixes and closed issues are complete, and `--since <ref>` to hunt only changed files.
  4. **Don't lose proven bugs:** in live mode, keep an offline-only proof as an offline draft (runs 12, 14 and 17); the browser prompt names only the accounts a test uses (Part 4 run).
  5. **Honest cost preview:** base it on the recorded runs (370k–1.8M processed tokens per hunter, not 100k) and show a range.
  6. **Outside check:** file 5–10 existing drafts upstream (godotenv exit code, json-server `_dependent` delete) and record whether each is accepted, fixed or closed as intended.
- [ ] Make `/audit` say whether code is safe to deploy, in three projects in this order (planned for the week of 2026-11-23). From the 2026-11-20 brainstorm; CI is skipped for now (2026-11-20)
  1. **Verdict and report:** build 2026-11-20-m-audit-verdict. Define is done and its design is approved; it stopped before Build. Resume with `/sdlc:start`, check the 12 ACs in `docs/sdlc/changes/2026-11-20-m-audit-verdict.md`, then build.
  2. **Stack coverage:** brainstorm it, then build it. It covers checklists for React, TypeScript, Go, Rust, Python and PHP; OSV-Scanner for every lockfile; and Semgrep hits as leads the auditors must confirm, asking the owner to install a missing tool when it's needed. It also adds checklist items for OWASP 2025 A04 and A06–A10.
  3. **Live `/audit --target`:** brainstorm it, then build it. It proves code findings and probes headers, CORS, rate limits and logout on dev or UAT through `live_proxy.py`, with two or more test users of different roles and writes allowed. Never production.

## Done

- [x] Won't fix, known limits or kept by decision (closed in the plan for the week of 2026-11-23, with the owner's OK) (2026-11-20)
  - Leak scan: a protocol-relative `//plainname` with no scheme isn't counted (known limit, README); a loopback alias on the target's port refuses a finding the masker would pass (C4-1, kept by decision); substring matching over-refuses longer names (the safe side); expanded IPv6 and punycode spellings; a 1 MB draft costs about 3 s and 97 MB to scan (bounded, R6-3).
  - Login word: rare prose still refused (`Auth: member`, `a bearer member`), the safe side.
  - oracle.py: `tests/test_oracle.py` hostile-input matrices beyond the minimal-testing rule.
- [x] `tests/test_departures.py:103` E501: already fixed, `uv run ruff check .` passes on `main` (2026-11-20)
