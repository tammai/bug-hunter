# 2026-11-06-m-windows-isolation
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-06-m-windows-isolation.md   (this feature's record for people)
Track: M   (sized up because: footprint 15 files across isolate, the hunt-path scripts and the test guard; footprint: 15 files)
Risk: high   (secrets and credential isolation; untrusted planted links reach file paths)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-06
Base: bc45a9d
Owner: tammai.it@gmail.com
Tool: claude-code
Verified: bc45a9d tree c608e479715968e02d9dd3e786591733fcf3e193
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, this session

## Handoff
- Windows Python uppercases os.environ keys; nt.environ keeps case and Git Bash is case-sensitive (unset ONEDRIVE leaves OneDrive)
- CreateProcess finds System32\bash.exe (WSL) before PATH; tests must use Git's bash from git --exec-path (parents[2]/usr/bin/bash.exe)
- Git Bash converts HOME and PATH to /c/... form inbound; values exported inside bash keep their Windows form
- Symlink creation needs privilege on this machine (WinError 1314); junctions don't (_winapi.CreateJunction)
- Git for Windows system config sets credential.helper and core.autocrlf; GIT_CONFIG_NOSYSTEM must hide it
- uv run uses Python 3.13 (cp1252 stdout); Git Bash python3 here is 3.15 (UTF-8 default)

## Tasks
1. **Test guard: no real gh** — —
   - Files: `tests/conftest.py`, `tests/test_post.py`
2. **isolate.py path fallback and Windows plan** — AC-001 AC-002 AC-003 AC-004 AC-005 AC-006 AC-007
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
3. **UTF-8 output on the hunt and audit path** — AC-008 AC-009
   - Files: `scripts/scope.py`, `scripts/drafts.py`, `scripts/known.py`, `scripts/findings.py`, `scripts/throwaway.py`, `scripts/secrets_scan.py`, `tests/test_scope.py`
4. **Baseline, todo and docs** — —
   - Files: `.sdlc/baseline.md`, `README.md`, `knowledge/gotchas/isolating-agents-without-a-sandbox.md`, `docs/sdlc/todo.md`

## Public Surface
- env `USERPROFILE APPDATA LOCALAPPDATA HOMEDRIVE HOMEPATH TEMP TMP (Windows exports of isolate.py)` — AC-003

## Gate log
- 2026-11-06 test guard built before Define, on the owner's order after the suite filed real issues #12-#17 (deleted by the coordinator); its test failed first with KeyError: 'GH_CONFIG_DIR', then passed; tests/test_post.py alone run offline (proxies to 127.0.0.1:9), issue list unchanged
- 2026-11-06 Stage 1: pass — spec and plan approved by the owner via the coordinator: TEMP/TMP redirected, fake-gh tests to baseline, fallback race accepted
- 2026-11-06 build: verify.py fails only on the test step: 16 failed, 122 passed, 3 skipped; all 16 are in .sdlc/baseline.md (Windows-only fixtures). Lint passes. The 9 AC tests and the gh guard test pass (10 passed). Same result from PowerShell. Step 4 and the hunt/audit dry run (Python 3.15 and 3.13) recorded in the change file.
- 2026-11-06 Stage 2: pass — verify fails only on the 16 baseline tests (Windows-only fixtures); lint, AC tests pass
- 2026-11-06 review: ran security (Risk high) and code high (Risk high; Public Surface not none); recommendation taken without asking: dispatched worker running unattended (headless rule)
- 2026-11-06 Stage 3: fail — round 1: security FAIL S1 S2 S3 (+S4 S5 low); code-review high: CR1 (=S1) high, CR2 CR3 CR4 medium bugs; all fixed test-first
- 2026-11-06 Stage 2: pass — round 1 fixes done test-first; verify fails only on the 16 baseline tests
- 2026-11-06 Stage 3: fail — round 2: code review FAIL R2-2 R2-3 R2-7; owner chose one more fix round; R2-1 and R2-4 kept as designed (tickets)
- 2026-11-06 Stage 2: pass — round 3 fixes R2-2 R2-3 R2-7 test-first; same 16 baseline failures only; POSIX evidence from WSL python 3.12: DIR_FD True, undecodable JAVA_HOME passes through
- 2026-11-06 Stage 3: pass — security r2 PASS, code r3 PASS; Learn: gotcha Windows section, 4 recurring defects, todo
- 2026-11-06 Stage 4: baseline failures waived: only the test step failed; 16 listed in .sdlc/baseline.md

## Deviations
- 2026-11-06 tests/conftest.py tests/test_post.py What: the gh guard was written before the change file. Why: the owner ordered it first, before any further test run, after the suite filed real issues. Effect: no AC for it; it is a must-never-break line backed by its test.
- 2026-11-06 .sdlc/baseline.md What: created with 16 Windows-only failing tests. Why: the owner chose to record pre-existing Windows test failures off the command path instead of fixing them here. Effect: Ship passes --waive-baseline; the fixes are the Windows test-suite todo.

## Open questions
-
