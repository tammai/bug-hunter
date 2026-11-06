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
Verified: ec6f5c2 tree f580f85deee190387066bbaa5a51e6035de97297
Slice: B4   Slice base: dc9f54e   Slice gates: none
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
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
- 2026-11-06 Stage 2: pass
- 2026-11-06 review: ran security, code high (Risk: high; L; Public Surface), self-chosen: L
- 2026-11-06 Stage 3: fail — review r1: security S1, S2 (+S3-S6); code H1-H4, M1-M4 (+L1-L4, F1); all fixed now
- 2026-11-06 Stage 2: pass

## Deviations
- 2026-11-06 scripts/scope.py What: the unsafe-folder warning now prints once per folder after both installs and audits, reading 'no install or audit for …'. Why: audits reuse the install rules, so the same folder warned twice. Effect: the existing count of 6 warnings in test_stacks still holds.
- 2026-11-06 .claude/rules/plugin-prompts.md What: rule updated to match constitution 1.1.0 (audit proof levels, audit findings never posted, <redacted>) and now loads for security/**. Why: the constitution skill flagged it as contradicting the amended Principle I. Effect: prompt-editing sessions get the right rule.
- 2026-11-06 commands/audit.md What: the secrets scan reads the repo itself, not the throwaway copy. Why: the copy (a clone) lacks local untracked .env files, which the scan must cover; the scan only reads. Effect: differs from the change file's flow step 3-4 wording (review F1).
- 2026-11-06 commands/audit.md, tests/test_plugin_files.py What: findings are screened with findings.py check before verifiers see them, and deduped with the new findings.py dedupe against earlier runs. Why: review S3 (an unscreened finding could carry a secret into a verifier prompt) and M4 (re-runs refiled scripted findings). Effect: AC-011's step-order test now has check before the verifier and dedupe before next.
- 2026-11-06 scripts/findings.py, scripts/secrets_scan.py, scripts/scope.py, scripts/stacks.json, tests/* What: review round 1 fixes: whole-value placeholder rule shared by scan and check; strict NAME=value env pattern in check; every REPORT.md and inventory line scrubbed; npm error JSON and missing results are failures; npm fix names the package to upgrade; meta validated; inventory skips the header, accepts outer pipes and merges earlier runs; fsync; per-line most-severe hit; $-prefixed values reported unless references; unreadable files skipped; AWS/private-key patterns case-sensitive; ignored dirs listed with --directory; lockfiles out of --focus security; composer audit --no-plugins --no-scripts. Why: review S1, S2, S4, S5, S6, H1-H4, M1-M3, L1-L4. Effect: the test that {} is a clean npm audit now expects a failure; AC-002's composer command changed.
- 2026-11-06 scripts/secrets_scan.py What: is_placeholder is a module function imported by findings.py. Why: the scanner and findings.py check must apply the same whole-value placeholder rule (review S2/S4). Effect: one definition of what counts as a placeholder.

## Open questions
-
