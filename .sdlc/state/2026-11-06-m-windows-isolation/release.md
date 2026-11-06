# Release: bug-hunter v0.3.1

- **Version:** v0.3.1, a patch release. `plugin.json` and `marketplace.json` were bumped to 0.3.1 in PR #20.
- **Environment:** GitHub release https://github.com/tammai/bug-hunter/releases/tag/v0.3.1, published 2026-11-06T10:18:17Z UTC (public repo).
- **Commit:** `bf6f913` on `main`, with CI green. It includes:
  - 2026-11-06-m-windows-isolation (PR #18);
  - 2026-11-06-s-command-frontmatter (PR #19). Before that fix, `claude plugin validate .` failed on the `/hunt` and `/audit` frontmatter, which already blocked v0.3.0's validate step.
- **Steps run** (per `knowledge/runbooks/release.md`):
  1. The owner ran `gh pr merge 18 --merge`. Then `gh pr merge 19 --merge` and `gh pr merge 20 --merge`.
  2. `git tag -a v0.3.1 -m "bug-hunter v0.3.1"` on `bf6f913`.
  3. `git push origin v0.3.1`.
  4. `gh release create v0.3.1 --title "bug-hunter v0.3.1" --notes-file release-notes-v0.3.1.md --verify-tag`, after the owner's explicit yes on the version, commit, notes and rollback.
- **Deviation:** the runbook's live-run step was skipped with the owner's yes. The release notes list it as a known issue.
- **Smoke test: pass.**
  - The release is published (not a draft), and the tag resolves to `bf6f913`.
  - A fresh clone at the tag passes `claude plugin validate .`, and both manifests say 0.3.1.
  - In Git Bash on Windows, `isolate.py` from that clone puts USERPROFILE in the scratch home.
  - **Not done:** updating the owner's installed plugin (`claude plugin marketplace update bug-hunter`, then `claude plugin update bug-hunter@bug-hunter`), and checking that `/hunt` reaches the cost question. Those change the owner's plugin install, which this work was told not to touch. The owner runs them.
- **Rollback:**
  - Never move or delete the tag.
  - A bad release: revert on `main` through a PR, then release v0.3.2.
  - Bad notes only: `gh release edit v0.3.1 --notes-file <fixed.md>`.
