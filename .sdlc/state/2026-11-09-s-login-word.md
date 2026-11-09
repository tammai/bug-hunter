# 2026-11-09-s-login-word
Status: done
Process: 3
Track: S   (footprint: 7 files)
Risk: high
Top model: opus
Base: c2c5fc0
Owner: tammai.it@gmail.com
Tool: claude-code
Current: Stage 4 – Ship

## Tasks
1. **Login words count only as credentials** — AC-001
   - Files: `scripts/drafts.py`, `scripts/live_proxy.py`, `tests/test_drafts.py`
2. **Version 0.4.0-rc.2 and CHANGELOG** — AC-001
   - Files: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `docs/sdlc/changes/2026-11-09-s-login-word.md`

## Public Surface
- none

## Gate log
- 2026-11-09 Stage 1: pass
- 2026-11-09 verify: only the 17 baselined Windows tests fail (diffed by name); security review 2 rounds, round-2 highs fixed and checked per brief
- 2026-11-09 Stage 2: pass

## Deviations
- 2026-11-09 Ship What: committed by hand on 2026-11-09-s-release-rc1, no push, no ship.py; full-lint fails only on pre-existing E501 tests/test_departures.py:103 Why: orchestrator brief (task_8551385d7944) Effect: no Verified line; E501 ticketed in docs/sdlc/todo.md

## Open questions
-
