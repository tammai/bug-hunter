# 2026-11-08-m-b0-live-validation
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-08-m-b0-live-validation.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 6 files)
Risk: low
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-08
Base: cb5683d
Owner: tammai.it@gmail.com
Tool: claude-code
Current: Stage 2 – Build

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [ ] 2 Build
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

## Deviations
- 2026-11-08 AC-003 added: What: tooling-only parts rank last in plain /hunt (scripts/scope.py, scripts/stacks.json, tests/test_scope.py). Why: coordinator relayed the user's decision (msg_283cc6435730) to fix /hunt picking setup.py first as a B0 defect. Effect: one more AC and task in this change.
- 2026-11-08 AC-004 added: What: 'author' no longer matches the auth keyword (scripts/scope.py, scripts/stacks.json, tests/test_audit_scope.py). Why: found in the B0 /audit preview on the realworld app. Effect: one more AC.
- 2026-11-08 AC-005 added: What: CommonMark fence reading in drafts.py/findings.py (scripts/drafts.py, scripts/findings.py, tests/test_drafts.py, tests/test_findings.py). Why: B0 run 1 dropped a proven draft whose traceback caret line toggled the fence. Effect: one more AC.
- 2026-11-08 fenced What: new function drafts.fenced (CommonMark code-block reader) imported by findings.py. Why: one rule for the three places that toggled fences by hand (AC-005). Effect: drafts.py gains one module-level function; no CLI change.
- 2026-11-08 AC-006 added: What: findings.py check --repo validates Where citations; /audit passes it; auditor prompt says repo-relative paths (scripts/findings.py, commands/audit.md, agents/security-auditor.md, tests/test_findings.py). Why: B0 run 5 kept an absolute-path duplicate and a line past EOF. Effect: one more AC, one new optional CLI flag.
- 2026-11-08 AC-006 revised: What: absolute paths inside the repo accepted; dedupe gains --repo. Why: rejecting them would have dropped run 5's finding 03. Effect: dedupe has one more optional flag.

## Open questions
-
