# Part plan: Security and PII audit B2

**Record:** `docs/sdlc/changes/2026-11-06-l-security-pii-audit.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **Secret patterns and scan** — AC-003
   - Files: `scripts/secret_patterns.json`, `scripts/secrets_scan.py`, `tests/test_secrets_scan.py`
   - Test first: `test_finds_secrets_without_printing_them`, `test_clean_repo_and_bad_input`, `test_guardrail_patterns_stay_in_sync` (fixtures build fake secrets at run time).
   - Then: scan tracked files plus untracked `.env*`, one finding per line (most specific pattern first), skip binaries, files over 1 MB, non-UTF-8, symlinks and `node_modules`/`vendor`; print path, line, pattern, length, committed and severity, never the value.

## Public Surface

- `scripts/secrets_scan.py <repo>` — AC-003
