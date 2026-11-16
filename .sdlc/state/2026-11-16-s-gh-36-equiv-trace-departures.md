# 2026-11-16-s-gh-36-equiv-trace-departures
Status: done
Process: 3
Track: S   (footprint: 13 files)
Risk: low
Top model: opus
Base: e9509ce
Owner: tammai.it@gmail.com
Tool: claude-code
Verified: e9509ce tree 4bfce77ae0b39982dfc05c8fcb82ba43b8134809
Current: Stage 4 – Ship

## Tasks
1. **Read a registry with equiv-trace:<name>** — AC-001
   - Files: `tests/test_departures.py`
2. **Vendor contracts 1.3.1** — AC-002
   - Files: `contracts/v1/CONTRACTS.md`, `contracts/v1/MANIFEST`, `contracts/v1/acceptance-manifest.schema.json`, `contracts/v1/contracts.py`, `contracts/v1/cost-line.schema.json`, `contracts/v1/criteria-lock.schema.json`, `contracts/v1/departures.schema.json`, `contracts/v1/finding.schema.json`, `contracts/v1/test_contracts.py`, `tests/test_contracts_vendor.py`, `CHANGELOG.md`

## Public Surface
- none

## Test lock
- `tests/test_contracts_vendor.py` sha256:209dcb0ec8b8fadf17742e6d112419ddde7541321e676bfb5b859812afdeb807
- `tests/test_departures.py` sha256:c4cefc1589d5e5b91ef0c671981c17ab4243a2265907d58b52f422f66dd1ebea

## Gate log
- 2026-11-16 Stage 1: pass
- 2026-11-16 Stage 4: baseline failures waived: only the test step failed; 19 listed in .sdlc/baseline.md
- 2026-11-16 Stage 2: pass — no review: S, low risk, no public surface

## Deviations
-

## Open questions
-
