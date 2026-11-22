# 2026-11-20-m-audit-verdict
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-20-m-audit-verdict.md   (this feature's record for people)
Track: L   (sized up because: several distinct parts: verdict, re-check/fixed tracking, accepted findings, Worth a look, OWASP, scope gaps, prompts; footprint: 12 files)
Risk: high   (secrets and PII in audit output; deploy go/no-go)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-20
Base: 51b6b35
Owner: tam.mai@bigin.vn
Tool: claude-code
Current: Stage 1 – Define

## Stages
- [ ] 1 Define   — the change file, the plan sections below
- [ ] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- findings.py _report builds REPORT.md: scripts/findings.py:406; dedupe key is category+CWE+root-cause path:line: scripts/findings.py:342
- checklist detection (vue via package.json dependency) to copy for react: scripts/scope.py:261, _depends_on at :197
- composer audit gives no fixed version (_from_composer_audit, scripts/findings.py:240); npm fixAvailable via _fix_text :194
- secrets_scan.py reads current files only, never git history: why committed secrets need a rotated line
- recurring defects: fingerprint-based secret checks, one-line CLI errors, no substring placeholder tests apply to every new output
- constitution amendment goes through sdlc:project-constitution (1.2.0 -> 1.3.0), not a hand edit

## Tasks
1. **Coverage facts in scope.py (react checklist, other_extensions, manifests without lockfile, dirty tree)** — AC-010
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_audit_scope.py`
2. **Verdict, gaps, accepted.md and OWASP table in findings.py report** — AC-001 AC-002 AC-003 AC-004 AC-009 AC-012
   - Files: `scripts/findings.py`, `scripts/owasp.json`, `tests/test_findings.py`
3. **Fixed tracking, stable identity and recheck command** — AC-005 AC-006 AC-007
   - Files: `scripts/findings.py`, `tests/test_findings.py`
4. **Worth a look: unconfirmed folder and report section** — AC-008 AC-012
   - Files: `scripts/findings.py`, `tests/test_findings.py`
5. **Prompts, constitution, README, PRD, CHANGELOG** — AC-011
   - Files: `commands/audit.md`, `agents/finding-verifier.md`, `docs/sdlc/constitution.md`, `docs/sdlc/prd.md`, `README.md`, `CHANGELOG.md`, `tests/test_plugin_files.py`

## Public Surface
- command `findings.py recheck` — AC-007
- config `accepted.md` — AC-004
- config `scope.py coverage fields` — AC-010

## Gate log
- 2026-11-20 Design approved by the user in brainstorming (2026-11-20). User asked to stop before Build: Define written, not advanced; resume with /sdlc:start to approve ACs and build.

## Deviations
-

## Open questions
-
