# Part plan: Security and PII audit B1

**Record:** `docs/sdlc/changes/2026-11-06-l-security-pii-audit.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **`--focus security`** — AC-001
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_audit_scope.py`
   - Test first: `test_focus_security_orders_widens_and_picks_checklists`.
   - Then: widen the file set (config and schema types, `.env*` but not examples, `migrations/`; no tests, lockfiles or `docs/`), stable-sort keyword parts first and renumber, tag `checklists` from `stacks.json`'s `security_checklists` and the nearest tracked `package.json`.
2. **`audits`** — AC-002
   - Files: `scripts/scope.py`, `scripts/stacks.json`
   - Test first: `test_lockfiles_give_dependency_audit_steps`.
   - Then: `audits` from `stacks.json`, through the same rules as `installs`.

## Public Surface

- `scripts/scope.py --focus security`; JSON `parts[].checklists`, `audits` — AC-001, AC-002
