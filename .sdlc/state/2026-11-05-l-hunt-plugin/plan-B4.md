# Part plan: bug-hunter plugin v1 B4

**Record:** `docs/sdlc/changes/2026-11-05-l-hunt-plugin.md` · **Backlog:** [backlog.md](backlog.md)

## Tasks

1. **Agents** — AC-010
   - Files: `agents/bug-hunter.md`, `agents/repro-verifier.md`, `tests/test_plugin_files.py`
   - Test first: `test_agents_are_read_only_and_name_draft_sections`.
   - Then: hunter (read-only, throwaway copy, fixed draft output) and verifier (the draft alone, one verdict line); tools Read, Grep, Glob, Bash.
2. **Edge-input lists** — AC-013
   - Files: `edge-inputs/generic.md`, `edge-inputs/python-cli.md`
   - Test first: `test_edge_input_lists_cover_the_brief`.
3. **/hunt** — AC-011
   - Files: `commands/hunt.md`
   - Test first: `test_hunt_command_shows_cost_before_hunting`.
   - Then: scope → known → cost and trust question → hunters → format check → verifiers → numbered drafts → report.
4. **README** — docs
   - Files: `README.md`

## Public Surface

- `/hunt [paths…] [--max N]` — AC-011
- agents `bug-hunter`, `repro-verifier` — AC-010
