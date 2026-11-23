# 2026-11-23-s-isolate-secret-names
Status: done
Process: 3
Track: S   (footprint: 2 files)
Risk: high
Top model: opus
Base: 8c21291
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 8c21291 tree 4cd5ffb0caf75e47424a8d53963bcf8d313d6be5
Current: Stage 4 – Ship

## Tasks
1. **Drop short password names** — AC-001
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`

## Public Surface
- none

## Test lock
- `tests/test_isolate.py` sha256:243d958d0250e85d79c3a2222386a007f1ee9b7a4778455d2e845389dc343bf6

## Gate log
- 2026-11-23 Stage 1: pass
- 2026-11-23 Stage 2: pass — security review: r1 FAIL S1, r2 PASS

## Deviations
- 2026-11-23 Track What: kept at S although .claude/rules/sdlc-sensitive.md asks M for secrets work. Why: a one-line pattern change in one file with one test. Effect: the security review that rule requires still runs.
- 2026-11-23 test-change tests/test_isolate.py What: AC-001's always-true PWD assertion removed; AC-002 added (name-rule tests). Why: security review round 1 S1 (bash sets PWD itself, so the line couldn't fail) and S2 (the whole class of short password names). Effect: PWD/OLDPWD now tested through the rule directly.
- 2026-11-23 test-change tests/test_isolate.py (round 2) What: AC-002 cases added (VPNPASS, SMBPASS, DBPWD, ROOTPWD, DB_PWD2, SMTP_PW1; kept: PWDEBUG, ENCOMPASS_HOME, SURPASS). Why: security review round 2 R2-1 (joined and digit-suffixed spellings). Effect: more cases only.

## Open questions
-
