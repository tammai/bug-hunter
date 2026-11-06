# /hunt and /audit frontmatter parses again

## Why

**Request (verbatim):** "I recommend fixing it first -> go ahead". This follows my report that `claude plugin validate .` fails during the v0.3.1 release.

**Proof:**
- `claude plugin validate .` on `main` (d6ddcee) reports `commands/hunt.md` and `commands/audit.md`: "YAML frontmatter failed to parse: YAML Parse error: Unexpected token. At runtime this command loads with empty metadata (all frontmatter fields silently dropped)."
- So both commands lose their description and argument hint.
- The release runbook requires validate to pass before a version bump.

**Root cause:** `argument-hint: [paths…] [--max N]` is a plain YAML value that starts with `[`. YAML reads it as a flow sequence, then hits the text after the closing `]`. `/hunt-post` is fine because its hint starts with `<`. This was already present in v0.3.0.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Quote both `argument-hint` values with double quotes | Changing the hint text so it doesn't start with `[` | The hint is shown to users as written; quoting keeps it identical |
| The test checks every command and agent file's frontmatter values are valid plain scalars or quoted (no leading YAML indicator, no `: ` or ` #` inside) | Running `claude plugin validate .` in the test | CI has no `claude` CLI, and scripts and tests stay stdlib-only, with no YAML parser |

## Acceptance criteria

- **AC-001** Every frontmatter value in `commands/*.md` and `agents/*.md` is either quoted or a plain YAML scalar that parses as the same text, so `/hunt` and `/audit` load their description and argument hint.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_plugin_files.py › test_command_and_agent_frontmatter_values_parse_as_written | `uv run pytest tests/test_plugin_files.py::test_command_and_agent_frontmatter_values_parse_as_written` |

## Must never break

- The hint text users see stays `[paths…] [--max N]`.

## Out of scope

- The validator's missing-icon warning (not an error).

## Review

No review ran: no trigger fired. AC-001 red then green; claude plugin validate . passes.
