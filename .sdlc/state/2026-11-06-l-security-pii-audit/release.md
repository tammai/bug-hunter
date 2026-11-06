# Release: bug-hunter v0.2.0

- **Version:** v0.2.0 (`plugin.json` and `marketplace.json` 0.2.0, bumped in PR #8)
- **Environment:** GitHub release https://github.com/tammai/bug-hunter/releases/tag/v0.2.0, published 2026-11-06T04:57:37Z UTC (public repo)
- **Commit:** `73cfd89` on `main` (CI green). It includes 2026-11-06-m-more-stacks (PR #6), 2026-11-06-l-security-pii-audit (PR #7), the marketplace manifest (PR #3) and the MIT license (PR #4).
- **Steps run** (per `knowledge/runbooks/release.md`):
  1. `git tag -a v0.2.0 -m "bug-hunter v0.2.0" 73cfd89`
  2. `git push origin v0.2.0`
  3. `gh release create v0.2.0 --title "bug-hunter v0.2.0" --notes-file release-v0.2.0.md --verify-tag`
- **Deviation:** the runbook's live-run step was skipped. The owner will run `/hunt` and `/audit` themselves, and the release notes list it as the first known issue.
- **Smoke test: pass.**
  - The release is published, and the tag resolves to `73cfd89`.
  - A fresh clone at the tag passes `claude plugin validate .` and has the `commands/`, `agents/` and `security/` files.
  - `claude plugin marketplace update bug-hunter` and `claude plugin update bug-hunter@bug-hunter` moved the owner's install from 0.1.0 to 0.2.0.
- **Rollback:** never move or delete the tag. Revert on `main` through a PR and release v0.2.1.
