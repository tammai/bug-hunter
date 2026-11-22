# Release: bug-hunter v0.5.2

- **Version:** v0.5.2. `plugin.json` and `marketplace.json` were bumped to 0.5.2 in PR #35, with the CHANGELOG entry in the same PR.
- **Environment:** GitHub release https://github.com/tammai/bug-hunter/releases/tag/v0.5.2, published 2026-11-12T04:38:22Z UTC (public repo, not a draft or prerelease).
- **Commit:** `e9509ce` on `main`, the merge of #35. CI was green: `verify` on ubuntu-latest and `invariants`. It ships:
  - 2026-11-09-m-scratch-tickets (PR #33, merged as `bef8e95`);
  - 2026-11-12-m-windows-seal-and-clean (PR #34, merged as `8b1b3ba`, with its Windows run of AC-004).
  - Neither was in v0.5.1, which was tagged from a commit before them.
- **Steps run** (per `knowledge/runbooks/release.md`, with the owner's go-ahead):
  1. **Live run** on `main` at `8b1b3ba`, on this repo: `claude -p "/hunt --max 1" --plugin-dir <clone> --permission-mode bypassPermissions`, continued with `--resume`. The owner chose this repo and this mode, as for v0.5.0.
     - The cost question was shown and waited for an answer.
     - One hunter ran on `.sdlc/ci/invariants.py`, and a verifier reproduced its bug from the draft alone: `check_baseline` matches names as substrings.
     - The run was cleaned (2.8 MB freed), and the fix-or-save question was asked.
     - "Save it" wrote draft 02, which passes `drafts.py check`.
     - No run folder was left, and `/hunt-post` was not run. The run cost about $1.06 in total.
  2. **PR #35** (`release: v0.5.2`): `claude plugin validate .` passes, `tests/test_smoke.py` passes, CI was green, then `gh pr merge 35 --merge`.
  3. **Tag:** `git tag -a v0.5.2 -m "bug-hunter v0.5.2"` on `e9509ce`, then `git push origin v0.5.2`.
  4. **Publish:** `gh release create v0.5.2 --title "bug-hunter v0.5.2" --notes-file <notes> --verify-tag`. The notes cover what was fixed, upgrading, known issues from both features' tickets, and how to install.
- **Deviation:** the live run used this repo, not the runbook's reference target (tammai/sdlc pre-fix), as for v0.5.0. It shows the flow, the cleanup and the save path work, not that a known bug is found; it did find and verify a new one.
- **Smoke test: pass.**
  - The release is published, and the tag resolves to `e9509ce`.
  - Installing into a throwaway config folder (`/plugin marketplace add tammai/bug-hunter`, then `/plugin install bug-hunter@bug-hunter`) gave version 0.5.2, with `audit`, `hunt` and `hunt-post` listed. Its `throwaway.py` matches `main`. The owner's own install was not touched.
  - That installed copy, loaded under the owner's login with `--plugin-dir` and a narrow tool allowlist, ran `/hunt --max 1` in a throwaway repo up to the cost question. The question was left unanswered, so nothing ran, and no run folder was left.
  - The pinned URL `https://raw.githubusercontent.com/tammai/bug-hunter/v0.5.2/scripts/scratch.py` matches `scripts/scratch.py`.
- **Follow-up:** draft 02 (the substring match in `.sdlc/ci/invariants.py`) is a bug in a file the sdlc plugin seeds. Report it to the sdlc plugin rather than patch the seeded copy here.
- **Rollback:** never move or delete the tag. Revert on `main` through a PR and release v0.5.3, with the problem under known issues. If only the notes are wrong: `gh release edit v0.5.2 --notes-file <fixed.md>`.
