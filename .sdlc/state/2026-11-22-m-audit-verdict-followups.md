# 2026-11-22-m-audit-verdict-followups
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-audit-verdict-followups.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 8 files)
Risk: high   (secrets, deploy verdict, untrusted target git config)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: 635113a
Owner: tam.mai@bigin.vn
Tool: claude-code
Current: Stage 2 – Build

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [ ] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one session; S8 first to ticket if context runs short

## Handoff
- legacy key: findings.py _identities :426-449; recheck pairing :1015-1022; dedupe seen_before :511-545
- report Accepted/Blocking lines: findings.py _report :815-850; no_fix read :810
- git calls to route through secrets_scan.run_git: scope.py :45 :286, secrets_scan.py :145, findings.py :947
- S6 probe: plain git status runs filter.<x>.clean from .git/config; blank via GIT_CONFIG_KEY_n works; required -> exit 128
- N9 changes test_scripted_findings_fixed_when_gone_but_committed_secrets_need_rotation (02 fixed only with a real --repo): record test-change deviation

## Tasks
1. **Report: accepted severity, since committed, fix now** — AC-001 AC-002 AC-003
   - Files: `scripts/findings.py`, `tests/test_findings.py`
2. **Shared git helper, inventory escaping, S6 filter blanking, lazy fetch** — AC-009 AC-010
   - Files: `scripts/secrets_scan.py`, `scripts/scope.py`, `scripts/findings.py`, `tests/test_audit_scope.py`
3. **Scan: local env in history counts as committed; id key without hard links** — AC-004 AC-008
   - Files: `scripts/secrets_scan.py`, `tests/test_secrets_scan.py`
4. **Identity: npm one finding per advisory; legacy pairing and rotated** — AC-005 AC-006
   - Files: `scripts/findings.py`, `tests/test_findings.py`
5. **recheck without --repo fails closed** — AC-007
   - Files: `scripts/findings.py`, `tests/test_findings.py`
6. **Seal the audit folder; audit.md seal, reap order, README** — AC-011
   - Files: `scripts/findings.py`, `commands/audit.md`, `README.md`, `tests/test_findings.py`, `tests/test_plugin_files.py`
7. **Split F3 test; knowledge doc** — AC-003
   - Files: `tests/test_findings.py`, `knowledge/gotchas/audit-facts-frozen-at-first-sight.md`

## Public Surface
- command `findings.py seal` — AC-011
- command `findings.py recheck --seal` — AC-011
- export `secrets_scan.run_git` — AC-009

## Test lock
- `tests/test_audit_scope.py` sha256:a9f85c3c060a4009cf753f312a973709c14c9619e85e956def29ffdd3de8c360
- `tests/test_findings.py` sha256:ef8e9f93cb8ffaa72bb4e0b28ff28d7b0db38dc0aa4c0784cbc3687c7a3f49d6
- `tests/test_secrets_scan.py` sha256:8971e415a73c832f00ec545808bd0fcddcc104162b80b896f6f7a1cc56918589

## Gate log
- 2026-11-22 owner answers: SR3-4 (a) committed only when git definitely says so; S8 (a) build it; R3-3 (a) show severity and raise; re-block proposal and S6 submodule half dropped; review deferred to the end by owner instruction, no ship.py
- 2026-11-22 Stage 1: pass — plan approved by the owner (high-risk M)
- 2026-11-22 build: verify PASS head 635113a tree d8539da9486113ff25b2d7d4f403e375d0043b82; review deferred to the end by owner instruction; committed on branch, not pushed
- 2026-11-22 review r1: security FAIL SEC-1, code FAIL H1 H2 M1; back to Build (already at Stage 2, so logged)
- 2026-11-22 review r1 tickets (not fixed): SEC-3 $RUN inputs (scope, found, verdicts) unsealed, audit.md wording now says so; SEC-4/L3 browser._tracked git ls-files not through run_git (browser.py must stay standalone); L4 recheck without --seal is silent in the report; L5 simplifications; L7 test gaps (AC-010/012 skipped on Windows)
- 2026-11-22 review r2: security FAIL H1 H2, code FAIL H-A H-B; owner chose one more fix round (already at Stage 2, logged)
- 2026-11-22 review r2 tickets (not fixed): L-A the report doesn't explain an ambiguous legacy pair; L-B GIT_NO_LAZY_FETCH floor kept at 2.45.1 as a margin (2.44.0 unverified offline)
- 2026-11-22 review r3: security PASS, code FAIL R3-H1; owner chose one more round
- 2026-11-22 review r3 tickets (not fixed): R3-L3 every submodule is a gap even outside scope; R3-L4/M-2 history_unknown reaches the report via the model (a script-carried version); single-branch clones; L-4; L-5; L-6 drafts.drafts_dir environment

## Deviations
- 2026-11-22 test-change tests/test_audit_scope.py What: the hostile repo gets a tracked app.js (scope.py refused a repo with no source files) and expects dirty False, not true-or-null; the partial-clone check asserts in_history is not False instead of rev-list exiting 0. Why: blanked filters that change nothing honestly read clean, so AC-010's 'dirty is true or null' wording was wrong for this fixture; with GIT_NO_LAZY_FETCH git can't read the missing tree and exits 128, which is the safe 'can't say'. Effect: AC-010 now asserts no marker, a correct dirty value, and the safe history answer.
- 2026-11-22 test-change tests/test_findings.py What: test_accepted_findings_expire_and_bad_lines_accept_nothing expects '01 (high) until 2999-12-31' (was '01 until'); test_scripted_findings_fixed_when_gone_but_committed_secrets_need_rotation passes a real --repo (make_repo with composer.lock) for the local secret to be fixed; test_orphaned_advisories_and_accepted_md_edge_lines is split into three (F3), its BOM assertion gaining '(high)'. Why: AC-001 adds the current severity to Accepted lines; AC-007 makes recheck without --repo keep a never-committed secret open. Effect: same behaviours checked, new shape.
- 2026-11-22 public surface run_git, in_history (scripts/secrets_scan.py) What: secrets_scan.run_git is the shared git helper, and secrets_scan.in_history (True, False or None when git can't say) replaces findings._in_history so the scan and recheck share one history check. Why: the plan's shared-helper decision; the scan's SR3-4 check and recheck's N9 check need the same tri-state answer. Effect: scope.py and findings.py import both from secrets_scan; findings._in_history is gone.
- 2026-11-22 docs/sdlc/changes/2026-11-22-m-audit-verdict-followups.md What: AC-011 says 'the end of its Scope section' instead of '§1'. Why: verify.py's trace read '§1' as a reference to a spec section. Effect: wording only, same criterion.
- 2026-11-22 docs/sdlc/changes/2026-11-22-m-audit-verdict-followups.md What: after the build, the record states the owner's answers (SR3-4, S8, R3-3, both proposals dropped), AC-010 reads 'dirty is what the files show with those filters blanked' instead of 'true or null' and names the partial-clone case as its test checks it, and N11's race is stated as a known narrow window (on POSIX the later rename replaces the earlier key). Why: the record must match the approval and the code. Effect: wording only; no code or test changed.
- 2026-11-22 docs/sdlc/changes/2026-11-22-m-audit-verdict-followups.md What: review round 1 fixes to the record: AC-001 and the R3-3 Decision say 'raised since it was first found' (H2; the code was right); R3-5 drops 'or the severity was raised since' (L2: not built, and a raise alone doesn't mean committed); N11's proof no longer names FAT/exFAT as fixed (L1: the privacy check refuses them); AC-011 seals after the owner's yes (M2, owner's decision); new AC-012 (SEC-1/H1), AC-013 (M1, L6), AC-014 (SEC-2). Why: review round 1 findings. Effect: three more acceptance tests; the seal moves in audit.md.
- 2026-11-22 test-change tests/test_findings.py What: AC-011's test expects the seal after the owner's yes and before the auditors, a two-part seal value (<owner's files>.<findings>), and --seal on the dedupe and report lines too; a module-level 'import re' was added. Why: review r1 M2 (owner's decision: seal after the yes) and SEC-2 (dedupe and report check the owner's files). Effect: AC-011 checks the new order and value; AC-014 covers the dedupe and report refusals.
- 2026-11-22 scripts/secrets_scan.py scripts/scope.py What: new git_version(), CONFIG_BY_VARIABLE and NO_LAZY_FETCH in secrets_scan (imported by scope); run_git always passes -c protocol.allow=never. Why: review r1 SEC-1/H1, older git ignores GIT_CONFIG_COUNT and GIT_NO_LAZY_FETCH silently. Effect: below 2.31 a repo defining its own filter reads dirty=null; below 2.45.1 a partial clone's history lookup is None; no transport runs on any git. browser.py's git ls-files is left out of run_git (it must stay standalone; ticket).
- 2026-11-22 test-change tests/test_audit_scope.py What: adds AC-012's test (old git fails closed, no transport runs) next to AC-009 and AC-010's. Why: review r1 SEC-1/H1. Effect: AC-009 and AC-010's tests are unchanged; the file's lock covers the new test too.
- 2026-11-22 scripts/browser.py What: _tracked's git ls-files drops GIT_DIR, GIT_WORK_TREE and GIT_INDEX_FILE, sets GIT_ALLOW_PROTOCOL to no protocol, and passes --no-optional-locks -c core.fsmonitor=false -c protocol.allow=never; nothing else in browser.py changes, and it stays stdlib-only and standalone. Why: review r2 M-A. Effect: the plugin's last unhardened git call; tested in AC-012.
- 2026-11-22 scripts/secrets_scan.py scripts/scope.py scripts/findings.py commands/audit.md README.md What: run_git sets GIT_ALLOW_PROTOCOL to a name no protocol has (NO_PROTOCOL), because protocol.allow=never is only a default a target's protocol.<name>.allow=always overrides (the earlier deviation's 'blocks every transport' was wrong); scope.py runs status with --ignore-submodules=all and reports coverage.submodules (optional in --scope; each is a gap); the scan marks a local .env whose history git can't answer history_unknown, /audit copies those paths to meta.json history_unknown, and the report lists each as a gap; _legacy_pairs drops produced secrets an open finding holds by id and groups siblings by legacy key with or without an id. AC-012 and AC-013 reworded; AC-015 (U1) and AC-016 (M1) added. Why: review r2 H1/H-A, H2/H-B, U1, M1. Effect: as listed; the 2.45.1 floor for GIT_NO_LAZY_FETCH is kept as a deliberate margin, since 2.44.0 support couldn't be verified offline.
- 2026-11-22 test-change tests/test_findings.py tests/test_audit_scope.py What: AC-013's test also checks B is byte-for-byte unchanged after dedupe and after a second run from the same scan; AC-012's test also sets protocol.file.allow and protocol.ext.allow to always before a fetch, and checks browser._tracked under an inherited GIT_DIR/GIT_WORK_TREE; AC-015 and AC-016's tests added. Why: review r2. Effect: stronger checks; no assertion weakened.
- 2026-11-22 scripts/findings.py scripts/secrets_scan.py scripts/scope.py scripts/browser.py commands/audit.md README.md docs/sdlc/changes/2026-11-22-m-audit-verdict-followups.md What: _legacy_pairs marks a pre-id finding None (kept open) whenever any produced secret shares its key, held by another finding or not (R3-H1); in_history answers None in a shallow clone, by the shallow file rev-parse --git-path names (M-1); run_git and browser._tracked take stdin from /dev/null with a 300 s timeout, a timeout reading as a failed call (L-2); browser._tracked drops all 15 repo variables via a copied frozenset (R3-L1); conflicted submodules listed once (R3-L2); a history_unknown finding's title says 'maybe committed before (git couldn't say)' (L-1); audit.md lists submodules in coverage (F1); the README's transport sentence names which calls it covers (F2); AC-017 and AC-018 added. Why: review r3. Effect: as listed.
- 2026-11-22 test-change tests/test_findings.py tests/test_audit_scope.py What: AC-017 and AC-018's tests added; no existing test changed. Why: review r3 R3-H1 and M-1. Effect: the files' locks cover the new tests.

## Open questions
-
