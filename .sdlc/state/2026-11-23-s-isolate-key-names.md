# 2026-11-23-s-isolate-key-names
Status: done
Process: 3
Track: S   (footprint: 2 files)
Risk: high
Top model: opus
Base: 7e54079
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 7e54079 tree 6688d8a6bf9e24d1058aa3da015dac64a6fc4353
Current: Stage 4 – Ship

## Tasks
1. **Drop key, PIN and session names** — AC-001
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`

## Public Surface
- none

## Test lock
- `tests/test_isolate.py` sha256:098d9d77a32219da009aaa9565b2b7d97118c4a41b9e62998daab8f3747318d1

## Gate log
- 2026-11-23 Stage 1: pass
- 2026-11-23 Stage 2: pass — security review: r1 FAIL, r2 PASS

## Deviations
- 2026-11-23 scripts/isolate.py What: the fix was written before the red run was recorded; the red run was then taken with isolate.py restored to main. Why: order slip. Effect: AC-001 still shown failing without the fix.
- 2026-11-23 test-change tests/test_isolate.py What: AC-001 cases added (digit suffixes, qualifiers, plurals, PIN_CODE, BW_SESSION, PAT, PSW/PASSW/PUK, COOKIE; kept: GPG_KEY_ID, SSH_KEY_PATH, session ids, COREPACK_ENABLE_AUTO_PIN). Why: security review round 1 S1-S5. Effect: more cases only.
- 2026-11-23 test-change tests/test_isolate.py (round 2) What: three desktop session flags added to the kept names. Why: security review round 2 R2-1. Effect: more cases only.

## Open questions
-
