# 2026-11-06-m-third-party-failures
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-06-m-third-party-failures.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 11 files)
Risk: low
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-06
Base: 36650f9
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 36650f9 tree f98c5f84f38c12b151d770bb101dfe246877fdf1
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- scope.py _tag has no repo path; tag integrations in _main like checklists (scripts/scope.py)
- Hunter Bash rules and installs live in agents/bug-hunter.md Hard rules; verifier step rules in agents/repro-verifier.md

## Tasks
1. **Stub server** — AC-001 AC-002
   - Files: `scripts/stub_server.py`, `tests/test_stub_server.py`
2. **Integrations tagging** — AC-003
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_stacks.py`
3. **Edge list and agents** — AC-004 AC-005
   - Files: `edge-inputs/integrations.md`, `agents/bug-hunter.md`, `agents/repro-verifier.md`, `tests/test_plugin_files.py`, `README.md`

## Public Surface
- scripts/stub_server.py --scenario <file> --log <file> — AC-001 AC-002
- scope.py edge_inputs value integrations — AC-003

## Gate log
- 2026-11-06 Stage 1: pass — plan not stopped for approval: low-risk M
- 2026-11-06 Stage 2: pass
- 2026-11-06 review: ran code default (Public Surface), not asked: low risk

## Deviations
- 2026-11-06 tests/test_plugin_files.py What: the every-stack edge-list test now allows integrations.md next to generic.md. Why: integrations is chosen by what a part calls, not by its stack, so stacks.json names it in its own integrations block. Effect: the test still fails on any other unnamed list.

## Open questions
-
