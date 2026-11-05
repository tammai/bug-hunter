# Part plan: bug-hunter plugin v1 B1

**Record:** `docs/sdlc/changes/2026-11-05-l-hunt-plugin.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **Shared test helpers** — AC-001–003
   - Files: `tests/conftest.py`
   - Then: a `make_repo` fixture (a real git repo in a temp dir whose name has a space and non-ASCII) and `run_script` (runs `scripts/<name>.py` as a CLI).
2. **scope.py** — AC-001, AC-002, AC-003
   - Files: `scripts/scope.py`, `tests/test_scope.py`
   - Test first: the three AC tests in `tests/test_scope.py`.
   - Then: `git ls-files -z`, filter to source files that aren't tests, group by directory in natural order, chunk by 5, cap with `--max`, print JSON; errors are one line on stderr.

## Public Surface

- `scripts/scope.py <repo> [paths…] [--max N]` — AC-001, AC-002, AC-003
