---
type: gotcha
title: A "copy" of a target repo can reach back into it
description: Why agents copy targets only with scripts/throwaway.py, and the git traps it avoids.
---

# A copy of a target repo can reach back into it

Agents make their copy only with `scripts/throwaway.py`, never `cp -R`. Each trap below cost a review round on 2026-11-05:

- **Worktrees:** a linked worktree's `.git` is a file holding an absolute `gitdir:`. `cp -R` keeps it, so a commit or checkout in the "copy" moves the real repo's refs and index. A `git clone --no-local --no-hardlinks` has its own object store.
- **Environments:** `.venv` shebangs and editable-install `.pth` files hold absolute paths back to the original, so code "run in the copy" runs and writes in the original. The clone leaves untracked folders out; agents build fresh environments inside the copy.
- **Remotes:** a clone's `origin` points at the real repo, so a repro's `git push` writes there. `throwaway.py` removes it and refuses if that fails.
- **Symlinks:** absolute or `..` links still point outside. `throwaway.py` refuses them.
- **The owner's git config:** porcelain `git diff` follows `diff.noprefix`, `color.diff=always` and external diff tools, giving patches `git apply` can't read. Pin `--no-ext-diff --no-textconv --no-color --src-prefix=a/ --dst-prefix=b/`.
- **Credentials:** agents run with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0`, `SSH_AUTH_SOCK` and the `gh` tokens unset, and `GH_CONFIG_DIR` in scratch.

From [2026-11-05-l-hunt-plugin](../../docs/sdlc/changes/2026-11-05-l-hunt-plugin.md).
