# 2026-11-22-m-isolate-followups
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-isolate-followups.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 3 files)
Risk: high   (secrets: agent isolation boundary; untrusted environment input)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: fdd1072
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: b4d953c tree 3a39610487a5b6cf80ed4e91178811f39ca2cdd1
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline in this session; the Windows-only checks (MSYS ssh with -F /dev/null) join the planned Windows session

## Handoff
- unset filter drops non-identifier names silently: scripts/isolate.py:258-261
- _refuse_links descriptor branch checks by path: scripts/isolate.py:346-352
- exports dict, where GIT_SSH_COMMAND and the stripped proxy values go: scripts/isolate.py:173-217
- isolated_env() dumps with compgen -e, which can't see non-identifier names: assert through a python child
- fail-closed decision (AC-004) waits on the owner's OK

## Tasks
1. **Isolation's own GIT_SSH_COMMAND** — AC-001 AC-002
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
2. **_refuse_links checks through its descriptor** — AC-003
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
3. **Fail closed on names bash can't unset** — AC-004 AC-005
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
4. **Proxy credentials stripped** — AC-006
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
5. **Gotcha doc** — AC-001
   - Files: `knowledge/gotchas/isolating-agents-without-a-sandbox.md`

## Public Surface
- env `GIT_SSH_COMMAND` — AC-001

## Test lock
- `tests/test_isolate.py` sha256:b714a5b583d720f949eb01f7949803cee1e7cbfb2cbe03381f8ee0e507a9cbae

## Gate log
- 2026-11-22 Stage 1: pass — plan approved by the owner (high-risk M)
- 2026-11-22 build done: verify PASS head 635113a tree 65feae28e3224a93f4f8c49644229d1b3744956b; review deferred by the owner to the end of the build (all lanes reviewed together); not advanced to Review
- 2026-11-22 review r1 (run by the coordinator after the deferred build): security FAIL S1, code FAIL CR1-1; back in Build (already at Stage 2) to fix S1, S2, CR1-1..CR1-6, CR1-8; S3/CR1-7 are tickets
- 2026-11-22 review r2 (coordinator): security FAIL R2-1, R2-2; code PASS. Owner chose one more fix round. Reports saved by the builder from the relay: .sdlc/.work/findings/2026-11-22-m-isolate-followups/security-r2.md, code-reviewer-r2.md
- 2026-11-22 review r3 (coordinator): security FAIL R3-1; owner chose the structural fix plus one more round. Report saved by the builder from the relay: .sdlc/.work/findings/2026-11-22-m-isolate-followups/security-r3.md
- 2026-11-22 review r4 (coordinator): security PASS, no high or medium; lows fixed without another round (L1, L3, L4, F1). Report saved by the builder from the relay: security-r4.md
- 2026-11-22 rebased onto origin/main fdd1072 (C3 and oracle merged), no conflicts; Base set to the merge-base fdd1072
- 2026-11-22 Stage 2: pass — reviews deferred by the owner to the end of all builds; run by the coordinator: r1-r4
- 2026-11-22 Stage 3: pass — security r4 PASS, code r2 PASS; lows fixed; Learn: gotcha + 2 recurring defects

## Deviations
- 2026-11-22 tests/test_isolate.py AC-005 What: AC-005 shares AC-004's test (test_a_variable_bash_cant_unset_stops_isolation) instead of its own. Why: AC-005 guards behaviour that already holds, so a test of its own passes before the code and the red step refuses it. Effect: the change file's AC-005 row names AC-004's test; the check is unchanged.
- 2026-11-22 scripts/isolate.py proxy rule What: credentials are cut at the last @ anywhere after the scheme, not the last @ in the authority as the Decisions row says. Why: a raw / in a password would end the authority early and leave the password in the value. Effect: never leaks; an @ in a proxy URL's path (not seen in practice) would mis-route rather than leak.
- 2026-11-22 AC-004 owner decision (CR1-3) What: fail closed only for an odd name that could carry a credential (secret name, GIT_*, ALWAYS_UNSET, or a proxy URL with credentials); an odd name that is only a path into the home passes through, as before. Why: the owner chose it at review r1; a JetBrains 'PyCharm Community Edition' in the Windows profile would otherwise stop every run. Effect: AC-004 as written in the change file ('or a path into the real home') and its Decisions row are superseded on that point.
- 2026-11-22 test-change tests/test_isolate.py What: test_a_variable_bash_cant_unset_stops_isolation drops the into-home 'tool-dir' case (it must now pass through, per CR1-3), and adds a non-ASCII secret name, an odd GIT_ name, two stuck names named in one line, and odd names that pass ('Tool Dir' into the home, '!C:'); the name check compares against the escaped form. Why: review r1 CR1-3, CR1-5, CR1-6, S2. Effect: stricter, except for the owner's CR1-3 decision.
- 2026-11-22 README.md, knowledge/gotchas/copying-a-target-repo.md What: the owner-facing isolation paragraph and the credentials line are updated. Why: review r1 CR1-8, docs that restate isolate.py's rules. Effect: docs only.
- 2026-11-22 scripts/isolate.py review r1 fixes What: _plan returns unset, functions, exports and stuck; exported bash functions are removed with unset -f (S1/CR1-2); one helper _shown (unicode_escape) escapes names in both error paths (CR1-1); every stuck name is listed (CR1-5); proxy lists split only before a scheme:// entry (CR1-4). Why: review r1. Effect: as listed.
- 2026-11-22 AC-004 wording What: AC-004 now reads 'an inherited variable that could carry a credential (secret name, GIT_*, always-dropped, or a proxy URL with a user or password) whose name bash can't unset stops isolation'; odd names holding only a path or setting pass through. Why: the owner's CR1-3 decision, restated as the coordinator asked at review r2. Effect: the change file's AC-004 text ('a path into the real home') is superseded; the tests already check the decided rule.
- 2026-11-22 scripts/isolate.py review r2 fixes What: R2-1, unset -f only for a BASH_FUNC_ value starting '() {', any other goes through the credential checks; R2-2, a proxy-list split is trusted only when every entry before the last @ is a plain URL, else one cut at the last @ (two credentialed entries now keep only the last host: mis-route, never leak); R2-4, the proxy credential check runs for every PROXY name not exported, even one already dropped. Why: review r2. Effect: as listed.
- 2026-11-22 test-change tests/test_isolate.py What: test_isolations_ssh_finds_nothing_in_the_owners_ssh_folder (AC-002) no longer skips on Windows; it uses the password database where there is one and the profile home otherwise. Why: review r2 R2-5, so real behaviour isn't skipped on one platform. Effect: the same asserts on every platform with an ssh client.
- 2026-11-22 scripts/isolate.py owner decision R3-1 What: proxy lists are no longer split; every PROXY value is cut once between its scheme and its last @, and _plain_entry is gone. Why: the owner's decision at review r3, since no split can tell a separator from one inside a password (digit passwords looked like host:port). Effect: supersedes the CR1-4 and R2-2 fixes; a credentialed GOPROXY list keeps only what follows its last @; an uncredentialed list is unchanged.
- 2026-11-22 scripts/isolate.py R3-2 What: a BASH_FUNC_ name takes the unset -f route only when its value starts with '() {' and it couldn't carry a credential (not secret-named, not GIT_*, not always-dropped, no credentialed PROXY value); otherwise it is stuck. Why: review r3 R3-2, the owner's call. Effect: an exported secret-named function (get_token, and git_author, which matches AUTH) now stops isolation again, reversing the S1 expectation of round 1.
- 2026-11-22 test-change tests/test_isolate.py What: test_proxy_lists_keep_every_entry becomes test_proxy_values_never_keep_part_of_a_password (every R3-1 shape with , | and space and a sentinel password, plus an unchanged uncredentialed GOPROXY); test_exported_bash_functions_are_removed_not_refused uses a home-path function (mkcd) instead of git_author/f_token; the functions test checks secret-named functions stop isolation and the BASH_FUNC_name() form leaves no function in a child. Why: review r3 R3-1, R3-2, R3-3. Effect: the tests follow the owner's decisions; AC tests re-shown red at base.
- 2026-11-22 scripts/isolate.py review r4 lows What: L4, when the cut-away part holds another ://, the surviving host takes the scheme of its own entry (a known proxy scheme at an entry's start) or none, instead of the first entry's; L3, the functions test also checks the %% form leaves no BASH_FUNC_greet variable in a child; L1 and F1, the gotcha and README wording. Why: review r4. Effect: routing of a credentialed list uses the right scheme; no password fragment can come back as a scheme.

## Open questions
-
