# Installable by name: a marketplace manifest, with the version checked in both manifests

## Why

**Request (verbatim):** "yes, start with step 1": the release runbook's one-time setup ([release.md](../../../knowledge/runbooks/release.md)). Add `.claude-plugin/marketplace.json`, and make the smoke test check that the manifests agree instead of hard-coding `0.1.0`.

With the marketplace file, people can install by name (`/plugin marketplace add tammai/bug-hunter`, then `/plugin install bug-hunter@bug-hunter`) instead of with `--plugin-dir`. A version bump is then one edit per manifest, and CI catches a mismatch.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| The marketplace and the plugin are both named `bug-hunter`, with `"source": "./"` | A separate marketplace repo | One repo, one plugin, the same shape as the sdlc and tammai-tools marketplaces |
| The marketplace entry carries `version`, which must equal `plugin.json`'s | No version in the marketplace file | The runbook bumps both; the test keeps them in step |
| No `license` field | MIT, like the other marketplaces | The repo has no LICENSE file; choosing one is the owner's call |

## Acceptance criteria

- **AC-001** Given `.claude-plugin/marketplace.json`, then it lists exactly one plugin, named `bug-hunter`, with `"source": "./"` and the same `version` as `.claude-plugin/plugin.json`, and the smoke test no longer hard-codes a version.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_smoke.py › test_marketplace_lists_the_plugin_at_the_manifest_version | `uv run pytest tests/test_smoke.py::test_marketplace_lists_the_plugin_at_the_manifest_version` |

## Must never break

- `claude plugin validate .` accepts the plugin and the marketplace.

## Out of scope

- Tagging or publishing a release; the repo's visibility; a LICENSE.

## Review

No review ran: no trigger fired. claude plugin validate . passed (one warning: no icon, only needed for a directory listing).
