# 2026-11-26-s-history-unknown-by-script
Status: done
Process: 3
Track: S   (footprint: 4 files)
Risk: low
Top model: opus
Base: 1cac0ca
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 1cac0ca tree 6c9716f00f07d7cdbb2fb8aae01a8209973c9768
Current: Stage 4 – Ship

## Tasks
1. **history_unknown carried from from-secrets-scan through recheck to the report** — AC-001, AC-002
   - Files: `scripts/findings.py`, `tests/test_findings.py`, `tests/test_audit_scope.py`, `commands/audit.md`

## Public Surface
- none

## Test lock
- `tests/test_audit_scope.py` sha256:e96eaf2d0eb98f161cc16559e0fa0b8a4fd1c13ec6343526834a733faf149599
- `tests/test_findings.py` sha256:c2e20b31f6f85541d4561c49bc0cbefe6d136c732309e1f08ad1af47553c5909

## Gate log
- 2026-11-26 Stage 1: pass
- 2026-11-26 Stage 2: pass — no review: no trigger fired

## Deviations
- 2026-11-26 tests/test_audit_scope.py What: test_an_unknown_history_for_a_local_secret_is_a_gap now goes through from-secrets-scan, recheck and report instead of a hand-written meta.json history_unknown Why: that meta field is gone; the test now proves the scripted path (AC-001) Effect: none on other tests

## Open questions
-
