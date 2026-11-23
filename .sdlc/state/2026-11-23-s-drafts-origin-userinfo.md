# 2026-11-23-s-drafts-origin-userinfo
Status: done
Process: 3
Track: S   (footprint: 2 files)
Risk: high
Top model: opus
Base: f35f70e
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: f35f70e tree 956c5b1bba78559df3b36cc78cedaad7e296478e
Current: Stage 4 – Ship

## Tasks
1. **Keep credentials out of the drafts folder** — AC-001
   - Files: `scripts/drafts.py`, `tests/test_drafts.py`

## Public Surface
- none

## Test lock
- `tests/test_drafts.py` sha256:e9511c1c69a170f499c5a1070eb7e2524378f11b2c0aa8b6fb5be96f8c8e9183

## Gate log
- 2026-11-23 Stage 1: pass
- 2026-11-23 Stage 2: pass — security review: 5 rounds, r5 PASS

## Deviations
- 2026-11-23 test-change tests/test_drafts.py What: AC-002 test added; the good-origin guard pins c#, a?b, Azure user name and a deep @. Why: security review round 1 H1 and M1. Effect: more cases only.
- 2026-11-23 test-change tests/test_drafts.py (round 3) What: three deeper-@ origins added to AC-002; a no-origin repo named me@work keeps its folder (new guard test). Why: security review round 2 R2-H1 and R2-M1; owner chose option A at the review cap. Effect: origins with @ before the last part are refused.
- 2026-11-23 test-change tests/test_drafts.py (round 4) What: the w@b pin moved from kept to refused; two last-part leaks added to AC-002. Why: security review round 3 R3-H1; owner chose option B at the review cap. Effect: any @ in an origin part is refused; no existing ~/.bug-hunter folder has one (checked).
- 2026-11-23 test-change tests/test_drafts.py (round 5) What: two query/fragment leaks added to AC-002. Why: security review round 4 R4-H1; owner chose one more round. Effect: the @ check runs on the raw text before any cut, in _origin_parts.

## Open questions
-
