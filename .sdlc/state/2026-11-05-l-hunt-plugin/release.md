# Release: bug-hunter v0.1.0

- **Version:** v0.1.0 (`plugin.json` and `marketplace.json` both 0.1.0)
- **Environment:** GitHub release, https://github.com/tammai/bug-hunter/releases/tag/v0.1.0 (published 2026-11-05T23:30:25Z UTC; private repo)
- **Commit:** `2f47de8` on `main` (CI `verify` and `invariants` green). It includes 2026-11-05-l-hunt-plugin, the README and release runbook (PR #2), and 2026-11-06-s-marketplace-manifest (PR #3).
- **Steps run** (per `knowledge/runbooks/release.md`):
  1. `git tag -a v0.1.0 -m "bug-hunter v0.1.0" 2f47de8`
  2. `git push origin v0.1.0`
  3. `gh release create v0.1.0 --title "bug-hunter v0.1.0" --notes-file release-v0.1.0.md --verify-tag`
- **Deviation:** the runbook's live `/hunt --max 1` before release wasn't done; the owner chose to release anyway. It's listed as the first known issue in the notes.
- **Smoke test: pass.**
  - The release is published (not a draft, not a prerelease).
  - Tag `v0.1.0` resolves to `2f47de8` on GitHub.
  - A fresh clone at the tag passes `claude plugin validate .`, both manifests read `0.1.0`, and `commands/` and `agents/` are present.
  - Not checked by the agent: installing through `/plugin marketplace add` and reaching `/hunt`'s cost question in an interactive session.
- **Rollback:** never move or delete the tag once someone may have installed it. Revert on `main` through a PR and release v0.1.1. Only right after publishing, with the owner's yes: `gh release delete v0.1.0 --yes && git push --delete origin v0.1.0`.
