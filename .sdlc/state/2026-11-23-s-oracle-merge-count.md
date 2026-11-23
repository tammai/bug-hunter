# 2026-11-23-s-oracle-merge-count
Status: done
Process: 3
Track: S   (footprint: 2 files)
Risk: low
Top model: opus
Base: 87824b1
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 87824b1 tree 094a29a980f9133e5f59a92d44ca61ae14161896
Current: Stage 4 – Ship

## Tasks
1. **Count a named merge's branch once** — AC-001
   - Files: `scripts/oracle.py`, `tests/test_oracle.py`

## Public Surface
- none

## Test lock
- `tests/test_oracle.py` sha256:9667f94f1ddd97c5c3275f1098034d2409f15d6eb80fd04d91cf4402ac5d2600

## Gate log
- 2026-11-23 Stage 1: pass
- 2026-11-23 Stage 2: pass — no review: no trigger fired

## Deviations
- 2026-11-23 scripts/oracle.py What: brought-in commits come from the parent links of the existing git log walk, not git rev-list. Why: test_git_runs_a_fixed_number_of_times caps git calls; a rev-list per merge broke it. Effect: same result, no extra git call.

## Open questions
-
