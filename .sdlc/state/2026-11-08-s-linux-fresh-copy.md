# 2026-11-08-s-linux-fresh-copy
Status: active
Process: 3
Track: S   (footprint: 2 files)
Risk: low
Top model: opus
Base: 7789477
Owner: tammai.it@gmail.com
Tool: claude-code
Current: Stage 2 – Build

## Tasks
1. **git runs from a folder that always exists** — AC-001
   - Files: `scripts/throwaway.py`
2. **Record** — AC-001
   - Files: `docs/sdlc/changes/2026-11-08-s-linux-fresh-copy.md`, `CHANGELOG.md`

## Public Surface
- none

## Gate log
- 2026-11-08 Stage 1: pass — S: bug proven by CI (Linux), red can't be recorded locally

## Deviations
- 2026-11-08 AC-001 red step: What: verify.py red not run locally. Why: the test passes on Windows (Git Bash keeps a deleted working folder usable); it failed on Linux CI, run 42459256915 on 7789477. Effect: red evidence is that CI run; green is checked on Windows locally and on Linux by CI after push.
- 2026-11-08 .sdlc/baseline.md What: names the baseline row added in 0.3.2, tests/test_scope.py › test_live_keeps_only_parts_serving_http (Windows-only shutil.rmtree PermissionError, fails on main too, added with the owner's OK; recorded in the B0 feature with pytest's :: form). Why: CI invariants run 42459256892 needs a Deviations line naming it in this form. Effect: none on code.

## Open questions
-
