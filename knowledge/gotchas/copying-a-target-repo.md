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
- **Line endings and git's variables:** the clone checks out with the caller's config (Git for Windows' system `core.autocrlf=true`), but the seal reads the base with system and global config pinned off, so `throwaway.py` passes the caller's `core.autocrlf` and `core.eol` to `git clone --config`; otherwise every text file reads as changed on Windows. Every git command it runs drops the repo-locating variables (`git rev-parse --local-env-vars`), which a hook or alias would otherwise point at another repo.
- **A shared base:** since 0.5.0 each run clones once (`$RUN/base`) and every agent copies it. Agents can reach the base, so `throwaway.py` seals it when made (`.git/bug-hunter-seal`: a hash of the small files under `.git`; a walk of the whole working tree, every entry's name, type, mode, size and modification time, refusing a nested `.git`, a pipe or a device; `git status --ignored` with the index flags; and the contents of every path status lists) and `--base` refuses a base whose seal no longer matches, which covers an edited file, a moved `HEAD`, a hook, `core.hooksPath` and every other text pointer in one check. Status alone is not enough: it names a path, not what it holds, and it hides what git doesn't track (a `.git` planted in a subfolder, a pipe, an empty folder, a submodule's files). It does not hash clean tracked files' contents (that would read the whole repo per copy), and code running as the owner can rewrite the seal too, so it catches accidents and a repro's side effects, not a repo written to defeat it.
- **Credentials:** agents run with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0`, `SSH_AUTH_SOCK` and the `gh` tokens unset, and `GH_CONFIG_DIR` in scratch.

From [2026-11-05-l-hunt-plugin](../../docs/sdlc/changes/2026-11-05-l-hunt-plugin.md).
