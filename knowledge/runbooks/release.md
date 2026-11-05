---
type: runbook
title: Releasing bug-hunter
description: How to cut a bug-hunter release: checks, version bump, tag, GitHub release, smoke test, rollback.
---

# Releasing bug-hunter

A release is a version tag `vX.Y.Z` on `main`, a GitHub release with notes, and the plugin installable at that version. `/sdlc:deploy` follows this runbook; nothing else releases.

## One-time setup (not done yet)

- [ ] **Marketplace file.** Add `.claude-plugin/marketplace.json` listing the plugin (`"source": "./"`, the same `version` as `plugin.json`), through sdlc as an S change. Until it exists, people can only install with `claude --plugin-dir <clone>`.
- [ ] **Smoke-test version check.** `tests/test_smoke.py` hard-codes the version. Change it to check that `plugin.json` and `marketplace.json` agree, so a bump is one edit per file and a mismatch fails CI.
- [ ] **Visibility.** The repo is private, so only people with access can install it. Making it public is the owner's decision; it isn't part of a release.

## When to release

- `main` is green in CI (`verify`, `invariants`).
- Every feature going out has `Status: done` in `.sdlc/state/` and a merged PR.
- A live run worked since the last release (below). The tests cover the scripts, but only a live run shows the agents still hunt and verify.

## Steps

Run from a clean clone of `main`, logged in to `gh` as a maintainer.

1. **Pick the version.** Semver, with `0.x` rules until 1.0:
   - patch for fixes;
   - minor for new commands, agents, edge-input lists or options;
   - changes to the drafts folder layout, the draft format or `posted.json`: minor, called out under **Breaking** in the notes.
2. **Live run.**
   - Load the release candidate: `claude --plugin-dir <this clone>`.
   - In a trusted repo you know has a bug (the reference target is tammai/sdlc at its pre-fix commit), run `/hunt --max 1`.
   - Pass: it shows the cost and waits for a yes, the hunter and verifier run, and every draft it writes passes `python3 scripts/drafts.py check <draft>`.
   - Don't run `/hunt-post` on a real repo just to test.
3. **Bump the version** in `.claude-plugin/plugin.json` (and `marketplace.json` once it exists). Open a PR titled `release: vX.Y.Z` and merge it once CI is green.
4. **Tag `main` at the merge commit:**
   ```
   git switch main && git pull --ff-only
   git tag -a vX.Y.Z -m "bug-hunter vX.Y.Z"
   git push origin vX.Y.Z
   ```
5. **GitHub release.** Write the notes from each shipped feature's change file (`docs/sdlc/changes/*.md`: Why, and Review's tickets as known issues), then:
   ```
   gh release create vX.Y.Z --title "bug-hunter vX.Y.Z" --notes-file <notes.md> --verify-tag
   ```
   The notes cover what's new, **Breaking** (drafts layout or format changes, and how to move old drafts), known issues, and how to install.
6. **Smoke test the release.**
   - Install it the way users do: through the marketplace once it exists, else `--plugin-dir` on a fresh clone at the tag.
   - Check that `/hunt` and `/hunt-post` are listed, and that `/hunt --max 1` reaches the cost question.
   - Answer no at the cost question, so nothing runs.
7. **Record it** in `.sdlc/state/<feature>/release.md` (version, steps, smoke-test result, rollback). Then run `state.py log <feature> "deployed vX.Y.Z to GitHub release: smoke test pass"`.

## Rollback

- **Never move or delete a published tag.** Someone may have installed it.
- **A bad release:** revert on `main` (`git revert <commit>`, through a PR), then release the next patch version (`vX.Y.Z+1`) with the problem under known issues in its notes.
- **Bad release notes only:** `gh release edit vX.Y.Z --notes-file <fixed.md>`.
- **Only when no one could have installed it yet** (minutes after publishing, private repo): `gh release delete vX.Y.Z --yes` and `git push --delete origin vX.Y.Z`. Only with the owner's yes.

## Go-ahead

Steps 4 and 5 publish. Before them, the agent shows the version, the commit, the notes and these rollback steps, and waits for the owner's explicit yes.
