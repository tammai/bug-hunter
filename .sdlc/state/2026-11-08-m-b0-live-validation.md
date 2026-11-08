# 2026-11-08-m-b0-live-validation
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-08-m-b0-live-validation.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 6 files)
Risk: high   (isolate.py is the agents' isolation boundary; reap.py turns agent-written files into kill calls)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-08
Base: cb5683d
Owner: tammai.it@gmail.com
Tool: claude-code
Verified: 2e2f627 tree 5aa1827236057019dd5e0461b793b8dd006875d6
Current: Stage 2 – Build

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline; target runs as headless child sessions only once the coordinator relays approval

## Handoff
- targets cloned under C:/Users/Admin/orca/workspaces/bh-b0/; never answer a /hunt or /audit cost prompt without the coordinator's relayed approval
- keyword test: scripts/scope.py _security_relevant (line ~135)

## Tasks
1. **Tiered security ranking** — AC-001
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_audit_scope.py`
2. **Run records** — AC-002
   - Files: `knowledge/runs/`, `knowledge/index.md`, `docs/specs/rebuild-upgrade/04-bug-hunter.md`

## Public Surface
- none

## Gate log
- 2026-11-08 Stage 1: pass — plan not stopped for approval: low-risk M; coordinator approved fixing defect 1 test-first (msg_97dd215aaf6b)
- 2026-11-08 pre-existing Windows failure not in baseline: tests/test_scope.py::test_live_keeps_only_parts_serving_http fails on main too (shutil.rmtree PermissionError on git's read-only objects, same cause as baseline's test_dir_names_never_collide_or_escape); needs the owner's OK to add to baseline
- 2026-11-08 risk raised to high: the change touches isolate.py (isolation boundary, eval'd output) and adds reap.py (agent-written PID files become kill calls); coordinator msg_274536ef2a74
- 2026-11-08 verify: only the test step fails; all 17 failures are listed in .sdlc/baseline.md (16 Windows-only + test_live_keeps_only_parts_serving_http, added with the owner's OK); lint passes, every AC red then green
- 2026-11-08 Stage 2: pass — baseline-only test failures (17 listed); lint green; ACs red then green
- 2026-11-08 review: ran code-reviewer (high) and security (code-reviewer, security section) (rows: Code high — Risk high; Code default — L-size diff, new CLI flags and reap.py; Security — Risk high, isolate.py output is eval'd), self-chosen: high risk, coordinator approved reviewers
- 2026-11-08 Stage 3: fail — code-reviewer r1 FAIL: H1 (killed subshell orphans its child before reap), H2 (long PID line crashes reap)

## Deviations
- 2026-11-08 AC-003 added: What: tooling-only parts rank last in plain /hunt (scripts/scope.py, scripts/stacks.json, tests/test_scope.py). Why: coordinator relayed the user's decision (msg_283cc6435730) to fix /hunt picking setup.py first as a B0 defect. Effect: one more AC and task in this change.
- 2026-11-08 AC-004 added: What: 'author' no longer matches the auth keyword (scripts/scope.py, scripts/stacks.json, tests/test_audit_scope.py). Why: found in the B0 /audit preview on the realworld app. Effect: one more AC.
- 2026-11-08 AC-005 added: What: CommonMark fence reading in drafts.py/findings.py (scripts/drafts.py, scripts/findings.py, tests/test_drafts.py, tests/test_findings.py). Why: B0 run 1 dropped a proven draft whose traceback caret line toggled the fence. Effect: one more AC.
- 2026-11-08 fenced What: new function drafts.fenced (CommonMark code-block reader) imported by findings.py. Why: one rule for the three places that toggled fences by hand (AC-005). Effect: drafts.py gains one module-level function; no CLI change.
- 2026-11-08 AC-006 added: What: findings.py check --repo validates Where citations; /audit passes it; auditor prompt says repo-relative paths (scripts/findings.py, commands/audit.md, agents/security-auditor.md, tests/test_findings.py). Why: B0 run 5 kept an absolute-path duplicate and a line past EOF. Effect: one more AC, one new optional CLI flag.
- 2026-11-08 AC-006 revised: What: absolute paths inside the repo accepted; dedupe gains --repo. Why: rejecting them would have dropped run 5's finding 03. Effect: dedupe has one more optional flag.
- 2026-11-08 baseline grew: What: tests/test_scope.py::test_live_keeps_only_parts_serving_http added to .sdlc/baseline.md. Why: Windows-only shutil.rmtree PermissionError, fails on main too; owner approved via coordinator (msg_6c5d2db5366a). Effect: Review and ship treat it as a known failure.
- 2026-11-08 AC-007 added: What: drafts.py check rejects the owner's home path (scripts/drafts.py, tests/test_drafts.py). Why: B0 run 7 draft 05 carried C:\Users\<owner>\... into a draft meant for a public issue. Effect: one more AC.
- 2026-11-08 AC-008 added: What: new scripts/reap.py (+ tests/test_reap.py), bg.pids rule in agents/bug-hunter.md, agents/repro-verifier.md, agents/security-auditor.md, agents/finding-verifier.md, reap step in commands/hunt.md and commands/audit.md. Why: B0 run 8 hunter left the target's node server running and rm -rf of the scratch failed. Effect: one new script and command step.
- 2026-11-08 AC-009 added: What: isolate.py's output sets an EXIT trap listing background jobs in bg.pids (scripts/isolate.py, tests/test_isolate.py). Why: B0 run 10 hunter left two unlisted servers running despite the bg.pids rule. Effect: one more AC.
- 2026-11-08 AC-010 added: What: reap.py stops the process tree under each listed PID (scripts/reap.py, tests/test_reap.py). Why: run 10's transcript shows the hunter listed and killed the PIDs, but one was a subshell whose node child survived. Effect: one more AC; AC-009's trap kept for forgotten jobs.
- 2026-11-08 AC-011, AC-012 added: What: review r1 H1/H2 fixes in scripts/reap.py, scripts/isolate.py, agents/*.md (tests/test_reap.py). Why: code-reviewer r1 FAIL. Effect: two more ACs.
- 2026-11-08 AC-013, AC-014 added: What: security r1 S1 (reap.py tool lookup), S2/S3 (findings.py citation resolve and echo) in scripts/reap.py, scripts/findings.py, tests/test_reap.py, tests/test_findings.py. Why: security-r1 FAIL. Effect: two more ACs.

## Open questions
-
