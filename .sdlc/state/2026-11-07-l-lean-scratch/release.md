# Release: bug-hunter v0.5.0

- **Version:** v0.5.0 (`plugin.json` and `marketplace.json` 0.5.0, bumped in PR #28; CHANGELOG entry in the same PR)
- **Environment:** GitHub release https://github.com/tammai/bug-hunter/releases/tag/v0.5.0, published 2026-11-09T11:22:49Z UTC (public repo)
- **Commit:** `edad884` on `main` (CI green: `verify` on ubuntu-latest and `invariants`). It includes 2026-11-07-l-lean-scratch (PR #27, merged as `811b9f1`).
- **Steps run** (per `knowledge/runbooks/release.md`):
  1. Live run on the branch before the merge: `claude -p "/hunt --max 1" --plugin-dir <clone> --permission-mode bypassPermissions` on this repo (the owner chose this repo and the bypass mode). Cost question shown and waited; one hunter and verifiers ran on `.sdlc/ci/invariants.py`; three verified drafts; run cleaned (2.7 MB freed) and the save question asked with nothing written; "save some: 1" saved draft `01`, which passes `drafts.py check`; no run folder left. `/hunt-post` not run.
  2. `gh pr merge 27 --merge`, then PR #28 (`release: v0.5.0`), `claude plugin validate .` passes, `tests/test_smoke.py` passes, CI green, `gh pr merge 28 --merge`.
  3. `git tag -a v0.5.0 -m "bug-hunter v0.5.0"` on `edad884`, `git push origin v0.5.0`, with the owner's explicit yes.
  4. `gh release create v0.5.0 --title "bug-hunter v0.5.0" --notes-file <notes> --verify-tag`.
- **Deviation:** the live run used this repo, which has no planted bug; the runbook's reference target (tammai/sdlc pre-fix) was not used. It showed the flow, the cleanup and the save path work, not that a known bug is found.
- **Smoke test: pass.**
  - The release is published (not a draft, not a prerelease) and the tag resolves to `edad884`.
  - `/plugin marketplace add tammai/bug-hunter` and `/plugin install bug-hunter@bug-hunter` into a throwaway config directory installed version 0.5.0, with `audit`, `hunt` and `hunt-post` listed. The owner's own install was not touched.
  - That installed copy loaded under the owner's login (`--plugin-dir`, a narrow tool allowlist) ran `/hunt --max 1` in a throwaway repo to the cost question; it was left unanswered, so nothing ran, and no run folder was left.
  - The pinned URL `https://raw.githubusercontent.com/tammai/bug-hunter/v0.5.0/scripts/scratch.py` matches `scripts/scratch.py`.
- **Rollback:** never move or delete the tag. Revert on `main` through a PR and release v0.5.1 with the problem under known issues; bad notes only: `gh release edit v0.5.0 --notes-file <fixed.md>`.
