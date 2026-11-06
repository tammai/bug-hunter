# 2026-11-06-l-security-pii-audit
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-06-l-security-pii-audit.md   (this feature's record for people)
Track: L   (sized up because: approach unclear at start; new agent type, finding format, report, constitution and PRD change; footprint: 22 files)
Risk: high   (security tooling: secrets handling, PII, agents running target code; amends the constitution)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-06
Base: e3cc6e3
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 5049441 tree eb2c310d74fc326f588a6c968929fe4f627c6dc6
Slice: B3   Slice base: 5049441   Slice gates: none
Current: Stage 2 – Build

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [ ] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, in parts (backlog): four parts too large for one session's context

## Handoff
- Constitution I conflicts with traced findings: amend via sdlc:project-constitution in B4, once the owner approves
- Reuse scope.py _safe_folder/_installs rules for audits (scripts/scope.py); drafts.numbered/next for numbering (scripts/drafts.py)
- Secret guardrail patterns: .claude/hookify/sdlc-secret-values.md line 9; keep scripts/secret_patterns.json in sync by test

## Tasks
1. **B1 scope --focus security, checklists, audits** — AC-001 AC-002
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_audit_scope.py`
2. **B2 secrets scan** — AC-003
   - Files: `scripts/secrets_scan.py`, `scripts/secret_patterns.json`, `tests/test_secrets_scan.py`
3. **B3 findings.py and guards** — AC-004 AC-005 AC-006 AC-007 AC-008
   - Files: `scripts/findings.py`, `scripts/post.py`, `scripts/known.py`, `tests/test_findings.py`
4. **B4 agents, checklists, /audit, constitution, PRD, README** — AC-009 AC-010 AC-011 AC-012
   - Files: `agents/security-auditor.md`, `agents/finding-verifier.md`, `security/generic.md`, `security/node.md`, `security/vue.md`, `security/pii.md`, `commands/audit.md`, `docs/sdlc/constitution.md`, `docs/sdlc/prd.md`, `README.md`, `tests/test_plugin_files.py`, `knowledge/index.md`

## Public Surface
- command /audit [paths] [--max N] — AC-011
- scripts/scope.py --focus security; JSON parts[].checklists, audits — AC-001 AC-002
- scripts/secrets_scan.py <repo> — AC-003
- scripts/findings.py check|dir|next|from-secrets-scan|from-npm-audit|from-composer-audit|inventory|report — AC-004..AC-007
- scripts/known.py --audit — AC-008
- agents security-auditor, finding-verifier — AC-009
- owner file ~/.bug-hunter/<host>/<owner>/<repo>/policy.md (optional) — AC-009 AC-011

## Gate log
- 2026-11-06 Stage 1: pass — change file approved by the user: amend constitution I for traced findings; report-only; optional owner policy.md

## Deviations
- 2026-11-06 scripts/scope.py What: the unsafe-folder warning now prints once per folder after both installs and audits, reading 'no install or audit for …'. Why: audits reuse the install rules, so the same folder warned twice. Effect: the existing count of 6 warnings in test_stacks still holds.

## Open questions
-
