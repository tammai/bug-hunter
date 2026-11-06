# Backlog: 2026-11-06-l-security-pii-audit

Record: `docs/sdlc/changes/2026-11-06-l-security-pii-audit.md` · Branch: `2026-11-06-l-security-pii-audit` · Each slice gets a short `plan-B<n>.md` when it starts and ends as one commit on the branch.

| ID | Slice | FRs | ACs | Deps | Size | Status |
|---|---|---|---|---|---|---|
| B1 | Scope for audits: `--focus security`, wider file set, checklists, `audits` | — | 1, 2 | — | S | done |
| B2 | `secrets_scan.py` and `secret_patterns.json` | — | 3 | — | M | done |
| B3 | `findings.py`: check, dir, next, from-* converters, inventory, report; `post.py` and `known.py --audit` guards | — | 4, 5, 6, 7, 8 | B2 | M | done |
| B4 | Agents, security checklists, `/audit`, constitution 1.1.0, PRD, README | — | 9, 10, 11, 12 | B1, B2, B3 | M | todo |
