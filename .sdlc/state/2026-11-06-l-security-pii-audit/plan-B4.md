# Part plan: Security and PII audit B4

**Record:** `docs/sdlc/changes/2026-11-06-l-security-pii-audit.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **Agents** — AC-009
   - Files: `agents/security-auditor.md`, `agents/finding-verifier.md`, `tests/test_plugin_files.py`
   - Test first: `test_audit_agents_are_read_only_isolated_and_adversarial`.
2. **Checklists** — AC-010
   - Files: `security/generic.md`, `security/node.md`, `security/vue.md`, `security/pii.md`
   - Test first: `test_security_checklists_cover_their_items`.
3. **/audit** — AC-011
   - Files: `commands/audit.md`
   - Test first: `test_audit_command_asks_first_and_never_posts`.
4. **Constitution 1.1.0, PRD, README** — AC-012
   - Files: `docs/sdlc/constitution.md` (through `sdlc:project-constitution`), `docs/sdlc/prd.md`, `README.md`, `knowledge/index.md`
   - Test first: `test_constitution_prd_and_readme_cover_audit`.

## Public Surface

- `/audit [paths…] [--max N]` — AC-011
- agents `security-auditor`, `finding-verifier` — AC-009
