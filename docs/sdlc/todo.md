# Todo

## Open

- [x] Leak check for word-like logins, review tickets left after round 2 of 2026-11-09-s-login-word (2026-11-09). Done in 2026-11-22-m-leak-check-followups (2026-11-22)
  - A word after a second word between field and value is missed: `<input name="password" value="member">`, `{"name":"token","value":"member"}`, `the password is member` (round 2, M-2).
  - A lowercase-only random token of 6–15 letters (`qwxzkvbnmt`) is treated as a word and counts only in credential context (round 2, L-2).

- [x] `oracle.py` (part 2) review tickets: the Citations and Scope groups, and the Efficiency and Reuse tickets that needed no file another lane owned. Done in 2026-11-22-m-oracle-tickets; what was left is the next item (2026-11-22)
- [ ] `oracle.py` tickets left by 2026-11-22-m-oracle-tickets (each needs `drafts.py`, `scope.py` or `contracts.py`, or wasn't asked for): 2026-11-22-m-oracle-tickets (2026-11-22)
  - the verifier's "Cited criteria" come only from the part's own criteria, while `drafts.py check` accepts any ID in the lock;
  - `classify_by_oracle` parses the spec twice (`drafts.oracle_problems` would return what it loaded);
  - four section parsers (`drafts.expected_body`, `finding_v1._sections`, `oracle._section`, `contracts._section`);
  - the max, budget and live cuts duplicated from `scope.py`;
  - `_repo_path` beside `scope._relative` (not equivalent: `_relative` resolves absolute paths and maps `docs_dir: "."` to the default);
  - the install warnings repeated from `scope._main`;
  - every commit message is read even when no record names a change (CR-9);
  - a named merge and its named branch commits are counted twice (CR-10);
  - `_git` doesn't pin `log.showRoot`, `log.diffMerges`, `diff.algorithm` or `GIT_DIR` (R2-3);
  - the all-history numstat walk's cost on large repos (R2-4);
  - the hunter's brief comes from the first criterion's story file only (R2-5);
  - contracts' `check_lock` and `check_criteria` read stories differently (R2-6).
- [ ] Leak scan and masker tickets, from the review of docs/sdlc/changes/2026-11-22-m-leak-scan-limits.md (C4-6, C4-8/S-7, trailing dots and S-5 are done there): 2026-11-22-m-leak-scan-limits (2026-11-22)
  - a response body cut before masking (SR1-5); sibling readers of repo files without the folder-link guard (SR1-6, L3); `..` in a spec path (SR1-7);
  - placeholders of other accounts, and a non-word login equal to the account name, refused (C3 CR4-3); a newline after "is:" ends the login look (CR4-5);
  - the non-session cookie rule's residual cases (L-3, SR2-5); a `news://` scheme and a comma after is/was (L-4); `password="" member` with no value key;
  - browser's `startswith("at ")` stack filter;
  - a 9-group IPv6 followed by another port (SR3-5); `::` and 127/8 beyond 127.0.0.1 as loopback (SR4-3); some ordinary links masked, not routed (SR4-4); tab, LF or CR end the userinfo look (SR4-5);
  - unquoted HTML attributes between a login's name and value.
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
- [x] Small `isolate.py` follow-ups from the Windows isolation review:
  - match 8.3 short names (needs `GetLongPathNameW`);
  - match a quoted value with a space inside the quotes;
  - give a one-line error instead of a traceback for an unpaired UTF-16 surrogate in a Windows env value, and fix that test's skip reason;
  - drop the extra `lstat` calls in the path fallback;
  - narrow the test guard's PATH filter so it stops hiding Homebrew's other tools on macOS.

  Review tickets (CR5, CR10, R3-1, R3-2, S4). Not bugs on the command path; 2026-11-06-m-windows-isolation (2026-11-06). Done in 2026-11-22-m-git-env-allowlist (2026-11-22)
- [x] `isolate.py` passes every other inherited `GIT_*` override through: `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `SSH_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_EXEC_PATH`, `GIT_TEMPLATE_DIR`, `GIT_EXTERNAL_DIFF`, `GIT_PAGER`/`GIT_EDITOR`, `GIT_CONFIG`/`GIT_CONFIG_SYSTEM`, and `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` (caught only when they point into the home; a `GIT_DIR` at the target would let a hunter edit it). Structural fix: unset every inherited `GIT_*` except an allowlist (`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, `GIT_TERMINAL_PROMPT`, `GIT_SSL_CAINFO`). Security review S1 of 2026-11-22-s-git-config-env (2026-11-22). Done in 2026-11-22-m-git-env-allowlist (2026-11-22)
- [x] `isolate.py` follow-ups from the review of 2026-11-22-m-git-env-allowlist (2026-11-22):
  - `GIT_SSL_CAPATH` and `GIT_PROXY_SSL_CAINFO` are now dropped, so git TLS breaks behind a corporate proxy that sets only those; keeping `GIT_SSL_CAPATH` was declined at Define, so revisit only if an owner hits it (R2-2, CR4);
  - plain `ssh` finds the owner's `~/.ssh` through the password database, not `HOME`, so git over SSH can still use the owner's keys; an isolation `GIT_SSH_COMMAND` with `-F /dev/null` and no identity would close it (CR5);
  - `_refuse_links` on the descriptor path checks entries by path (`os.path.islink(folder / name)`), not through the opened descriptor (R2-7);
  - variable names that aren't shell identifiers (`npm_config_//registry.npmjs.org/:_authToken`) can't be unset, so they survive; proxy URLs with credentials pass through (security, outside the diff).

  Done in 2026-11-22-m-isolate-followups (2026-11-22); `GIT_SSL_CAPATH` and `GIT_PROXY_SSL_CAINFO` stay declined. Its review tickets are the next item.
- [ ] `isolate.py` review tickets from 2026-11-22-m-isolate-followups (2026-11-22):
  - secrets in names `SECRET_NAME` misses: `PROXY_PASS`, `PROXY_PWD`, `SSHPASS`, `MYSQL_PWD` (S3, CR1-7);
  - odd names for key or cert files: the owner decides whether they stop isolation (R2-3);
  - an odd PROXY name holding a harmless `@` stops isolation; it fails closed (R3-4);
  - `BASH_FUNC_token+x%%` is refused rather than removed; the safe side;
  - bash 5 keeps a failed `%%` function import as a variable; only a home path can survive that way (L2);
  - Windows session: Git for Windows' ssh with `-F /dev/null`, real `=C:` and JetBrains variables, and the AC-001 fake-ssh and function-body tests under Git Bash.
- [ ] Improve how well `/hunt` finds bugs, in this order (planned to start the week of 2026-11-23); from the 19 B0 runs in `knowledge/runs/`, which measured only that kept drafts reproduce, not missed bugs or maintainer acceptance (2026-11-20)
  1. **Scoring benchmark:** 2–3 pinned repos per stack, about 10 planted bugs each with no hints in comments; score how many it finds, how many kept drafts are wrong, how often the verifier passes a bad draft, and cost per real bug. Run before and after each change.
  2. **Stricter verifier:** a checklist (every claim shown in its output, every cited line holds the quoted code), a script that checks line contents rather than just that the line exists, and bad drafts planted in the benchmark (defects 5, 8 and 10).
  3. **More bugs per run:** two hunters with different focus per part (input edge cases vs state and error paths), checking whether recent fixes and closed issues are complete, and `--since <ref>` to hunt only changed files.
  4. **Don't lose proven bugs:** in live mode, keep an offline-only proof as an offline draft (runs 12, 14 and 17); the browser prompt names only the accounts a test uses (Part 4 run).
  5. **Honest cost preview:** base it on the recorded runs (370k–1.8M processed tokens per hunter, not 100k) and show a range.
  6. **Outside check:** file 5–10 existing drafts upstream (godotenv exit code, json-server `_dependent` delete) and record whether each is accepted, fixed or closed as intended.
- [ ] Make `/audit` say whether code is safe to deploy, in three projects in this order (planned for the week of 2026-11-23). From the 2026-11-20 brainstorm; CI is skipped for now (2026-11-20)
  1. **Verdict and report:** build 2026-11-20-m-audit-verdict. Define is done and its design is approved; it stopped before Build. Resume with `/sdlc:start`, check the 12 ACs in `docs/sdlc/changes/2026-11-20-m-audit-verdict.md`, then build. Done in 2026-11-20-m-audit-verdict (2026-11-22).
  2. **Stack coverage:** brainstorm it, then build it. It covers checklists for React, TypeScript, Go, Rust, Python and PHP; OSV-Scanner for every lockfile; and Semgrep hits as leads the auditors must confirm, asking the owner to install a missing tool when it's needed. It also adds checklist items for OWASP 2025 A04 and A06–A10.
  3. **Live `/audit --target`:** brainstorm it, then build it. It proves code findings and probes headers, CORS, rate limits and logout on dev or UAT through `live_proxy.py`, with two or more test users of different roles and writes allowed. Never production.
- [ ] `/audit` verdict follow-ups, from the reviews of 2026-11-20-m-audit-verdict (2026-11-22):
  - an acceptance written for a finding's lower severity keeps accepting it after a `severity now` raise; show each accepted number's current severity in the Accepted list (R3-3, SR3-3);
  - a secret raised by a later commit still reads "in a local file, not committed" in its title and Impact; add "since committed" in the report (R3-5, SR3-8);
  - other facts frozen at first sight: "no fix known" after a fix is released (R3-6); a secret first seen after `git rm --cached` is rated low for good, though `_in_history` could raise it (SR3-4);
  - the transition run after the upgrade: a legacy (no-id) secret can absorb a rotated key at the same path, or two same-shape keys in one file (N4, N8, SR2-9);
  - npm advisory identity depends on the order of `via` (M6, unconfirmed);
  - `recheck` without `--repo` skips the git-history check (N9; `/audit` always passes it);
  - `secret-id.key` can't be made on a filesystem without hard links (N11, unconfirmed);
  - PII inventory cells and the pre-existing git calls in `scope.py` and `secrets_scan.py` aren't hardened like the new code (control characters, inherited `GIT_DIR`) (N12, SR2-5, SR3-2);
  - git config of a hostile target repo: `git status` filters and a treeless partial clone's lazy fetch can run its programs (S6, SR3-6, unconfirmed);
  - agents could edit `accepted.md` or the audit folder during a run, and nothing detects it (S8);
  - split `test_orphaned_advisories_and_accepted_md_edge_lines` into one behaviour per test (F3).

## Done

- [x] Won't fix, known limits or kept by decision (closed in the plan for the week of 2026-11-23, with the owner's OK) (2026-11-20)
  - Leak scan: a protocol-relative `//plainname` with no scheme isn't counted (known limit, README); a loopback alias on the target's port refuses a finding the masker would pass (C4-1, kept by decision); substring matching over-refuses longer names (the safe side); expanded IPv6 and punycode spellings; a 1 MB draft costs about 3 s and 97 MB to scan (bounded, R6-3).
  - Login word: rare prose still refused (`Auth: member`, `a bearer member`), the safe side.
  - oracle.py: `tests/test_oracle.py` hostile-input matrices beyond the minimal-testing rule.
- [x] `tests/test_departures.py:103` E501: already fixed, `uv run ruff check .` passes on `main` (2026-11-20)
- [x] `scratch.py clean` on Windows can't remove a read-only folder: `tests/test_scratch.py::test_clean_reports_size_and_removes_read_only_trees` fails with "Access is denied" on `hunter-1/home/go/pkg/mod/example.com@v1` (Go makes its module cache read-only), on `main` (v0.5.0) too, so a hunt's run folder on Windows is left partly behind. Its own S fix; baselined in 2026-11-09-m-scratch-tickets (2026-11-11). Done in 2026-11-12-m-windows-seal-and-clean; passes on Windows (2026-11-12)
- [x] Decide whether `isolate.py` should also unset inherited `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT` and `GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*`, which can inject git config (a credential helper) without any file — found in the Windows isolation change, not asked for there (2026-11-06). Done in 2026-11-22-s-git-config-env (2026-11-22)
- [x] Live-target tokens in `targets.json` expire mid-workflow: the CRM rebuild's bearer tokens last ~15 minutes, so someone ran a scratch script before every `/hunt` to mint fresh ones. Options: a token-refresh hook (a command `targets.json` names, run before the hunt and on a 401), or account credentials in `targets.json` so the hunter signs in itself (weigh against the secrets rules in `.claude/rules/sdlc-sensitive.md`). Raised by product-rebuild, CRM S1–S4 issue list item 5e (crm-workbench `plan/drafts/product-rebuild-issues-S1-S4.md`, commit 1f60997); evidence from crm-rebuild-sdlc-23 (2026-11-17). Done in 2026-11-17-m-token-refresh with the refresh command (2026-11-17)
