# Release: bug-hunter v0.6.0

- **Version:** v0.6.0. `plugin.json` and `marketplace.json` were bumped to 0.6.0 in PR #40 (`release: v0.6.0`), with the CHANGELOG entry in the same PR.
- **Environment:** GitHub release https://github.com/tammai/bug-hunter/releases/tag/v0.6.0, published 2026-11-17 (public repo).
- **Commit:** `51b6b35` on `main` (the merge of PR #40). CI was green: `verify` on ubuntu-latest and `invariants`. It includes 2026-11-17-m-token-refresh (PR #39, merged as `17fc888`).
- **Requested by:** the product-rebuild session asked for a release on the owner's behalf. The owner approved it in this session: first v0.6.0, then the publish go-ahead.
- **Steps run** (per `knowledge/runbooks/release.md`):
  1. Version picked: minor, because the change adds the `refresh` option to `targets.json`.
  2. Live run: **skipped by the owner's choice** (deviation, below).
  3. PR #40 bumped both manifests and the CHANGELOG. `claude plugin validate .` and `tests/test_smoke.py` passed, CI went green, and the PR was merged with `gh pr merge 40 --merge`.
  4. `git tag -a v0.6.0 -m "bug-hunter v0.6.0"` on `51b6b35`, then `git push origin v0.6.0`, with the owner's explicit yes.
  5. `gh release create v0.6.0 --title "bug-hunter v0.6.0" --notes-file .sdlc/.work/notes-v0.6.0.md --verify-tag`.
- **Deviations:**
  - No live `/hunt --max 1` run before the release; the owner chose to skip it. The release notes say so under known issues.
  - The smoke test didn't run `/hunt --max 1` to the cost question, which would need a headless `claude -p` run. Only the install was checked.
  - `.sdlc/config.json` has no `deploy` section. `scaffold.py deploy` printed target `null` and a default runbook path, `knowledge/runbooks/deploy.md`, that doesn't exist. The release followed `knowledge/runbooks/release.md`, the project's own release path. `/sdlc:setup deploy` could record it.
- **Smoke test: pass (install only).**
  - The release is published, not a draft or prerelease, and tag `v0.6.0` resolves to `51b6b35`.
  - `claude plugin marketplace add tammai/bug-hunter` and `claude plugin install bug-hunter@bug-hunter` installed version 0.6.0 into a throwaway `CLAUDE_CONFIG_DIR`, with commands `audit`, `hunt` and `hunt-post`. The installed `scripts/live_proxy.py` has the refresh code. The owner's own install wasn't touched.
- **Rollback:** never move or delete the tag. Revert on `main` through a PR and release v0.6.1 with the problem under known issues. For bad notes only: `gh release edit v0.6.0 --notes-file <fixed.md>`.
