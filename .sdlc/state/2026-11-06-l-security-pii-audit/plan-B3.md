# Part plan: Security and PII audit B3

**Record:** `docs/sdlc/changes/2026-11-06-l-security-pii-audit.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **findings.py** — AC-004, AC-005, AC-006, AC-007
   - Files: `scripts/findings.py`, `tests/test_findings.py`
   - Test first: the four `test_findings.py` AC tests.
   - Then: `check` (format, values, secret patterns via `secrets_scan`'s patterns), `dir` (0700, sibling of drafts), `next`, `from-secrets-scan`, `from-npm-audit` (npm 6 and 7+), `from-composer-audit`, `inventory` (merge PII blocks per field), `report` (atomic, 0600, with `--meta`).
2. **Guards** — AC-008
   - Files: `scripts/post.py`, `scripts/known.py`
   - Test first: `test_audit_findings_never_post_or_query_issues`.
   - Then: `post.py` refuses a file with a `**Proof:**` line before calling `gh`; `known.py --audit` lists the audit folder's titles without calling `gh`.

## Public Surface

- `scripts/findings.py check|dir|next|from-secrets-scan|from-npm-audit|from-composer-audit|inventory|report` — AC-004..AC-007
- `scripts/known.py --audit` — AC-008
