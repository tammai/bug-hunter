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

## Deviations
- 2026-11-22 test-change tests/test_audit_scope.py What: the hostile repo gets a tracked app.js (scope.py refused a repo with no source files) and expects dirty False, not true-or-null; the partial-clone check asserts in_history is not False instead of rev-list exiting 0. Why: blanked filters that change nothing honestly read clean, so AC-010's 'dirty is true or null' wording was wrong for this fixture; with GIT_NO_LAZY_FETCH git can't read the missing tree and exits 128, which is the safe 'can't say'. Effect: AC-010 now asserts no marker, a correct dirty value, and the safe history answer.
- 2026-11-22 test-change tests/test_findings.py What: test_accepted_findings_expire_and_bad_lines_accept_nothing expects '01 (high) until 2999-12-31' (was '01 until'); test_scripted_findings_fixed_when_gone_but_committed_secrets_need_rotation passes a real --repo (make_repo with composer.lock) for the local secret to be fixed; test_orphaned_advisories_and_accepted_md_edge_lines is split into three (F3), its BOM assertion gaining '(high)'. Why: AC-001 adds the current severity to Accepted lines; AC-007 makes recheck without --repo keep a never-committed secret open. Effect: same behaviours checked, new shape.
- 2026-11-22 public surface run_git, in_history (scripts/secrets_scan.py) What: secrets_scan.run_git is the shared git helper, and secrets_scan.in_history (True, False or None when git can't say) replaces findings._in_history so the scan and recheck share one history check. Why: the plan's shared-helper decision; the scan's SR3-4 check and recheck's N9 check need the same tri-state answer. Effect: scope.py and findings.py import both from secrets_scan; findings._in_history is gone.
- 2026-11-22 docs/sdlc/changes/2026-11-22-m-audit-verdict-followups.md What: AC-011 says 'the end of its Scope section' instead of '§1'. Why: verify.py's trace read '§1' as a reference to a spec section. Effect: wording only, same criterion.
- 2026-11-22 docs/sdlc/changes/2026-11-22-m-audit-verdict-followups.md What: after the build, the record states the owner's answers (SR3-4, S8, R3-3, both proposals dropped), AC-010 reads 'dirty is what the files show with those filters blanked' instead of 'true or null' and names the partial-clone case as its test checks it, and N11's race is stated as a known narrow window (on POSIX the later rename replaces the earlier key). Why: the record must match the approval and the code. Effect: wording only; no code or test changed.

## Open questions
-
