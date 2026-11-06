# Release: bug-hunter v0.3.0

- **Version:** v0.3.0 (`plugin.json` and `marketplace.json` 0.3.0, bumped in PR #10)
- **Environment:** GitHub release https://github.com/tammai/bug-hunter/releases/tag/v0.3.0, published 2026-11-06T07:29:28Z UTC (public repo)
- **Commit:** `156f549` on `main` (CI green). It includes 2026-11-06-m-third-party-failures (PR #9).
- **Steps run** (per `knowledge/runbooks/release.md`):
  1. `gh pr merge 10 --merge --delete-branch`
  2. `git tag -a v0.3.0 -m "bug-hunter v0.3.0"` on `156f549`
  3. `git push origin v0.3.0`
  4. `gh release create v0.3.0 --title "bug-hunter v0.3.0" --notes-file release-v0.3.0.md --verify-tag`
- **Deviation:** the runbook's live-run step was skipped. The owner will run `/hunt` themselves, and the release notes list it as the first known issue.
- **Smoke test: pass.**
  - The release is published (not a draft), and the tag resolves to `156f549`.
  - The pinned stub URL drafts use, `https://raw.githubusercontent.com/tammai/bug-hunter/v0.3.0/scripts/stub_server.py`, downloads and matches `scripts/stub_server.py`.
  - A fresh clone at the tag passes `claude plugin validate .` and has `scripts/stub_server.py` and `edge-inputs/integrations.md`.
  - `claude plugin marketplace update bug-hunter` and `claude plugin update bug-hunter@bug-hunter` moved the owner's install from 0.2.0 to 0.3.0.
- **Rollback:** never move or delete the tag. Revert on `main` through a PR and release v0.3.1; bad notes only: `gh release edit v0.3.0 --notes-file <fixed.md>`.
