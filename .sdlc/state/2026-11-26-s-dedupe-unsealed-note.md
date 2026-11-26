# 2026-11-26-s-dedupe-unsealed-note
Status: done
Process: 3
Track: S   (footprint: 3 files)
Risk: low
Top model: opus
Base: f1ba474
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: f1ba474 tree 8e2f1c46597b58aa89251c786cb8362de1a338d1
Current: Stage 4 – Ship

## Tasks
1. **dedupe --out records sealed; report --dedupe notes an unsealed dedupe; audit.md passes both** — AC-001
   - Files: `scripts/findings.py`, `commands/audit.md`, `tests/test_findings.py`

## Public Surface
- none

## Test lock
- `tests/test_findings.py` sha256:6bcd0eb5eb93d00eb7d992c04096bfbf2c4a3d1da2ba617e6a2fc7099ff66b06

## Gate log
- 2026-11-26 Stage 1: pass
- 2026-11-26 Stage 2: pass — no review: no trigger fired

## Deviations
- 2026-11-26 test-change tests/test_findings.py What: AC-001's test also checks a --dedupe file without sealed is refused with a message, not a traceback. Why: the scripts rule asks for missing-JSON-key coverage.

## Open questions
-
