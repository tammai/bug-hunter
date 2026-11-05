# Recurring defects

One line per defect: what it looks like, then the severity.

- A record of an outside action (an issue filed, a message sent) written after the action with no write check beforehand, no fsync and no fallback, so a failed write repeats the action next run: high
- A target repo copied with `cp -R` (worktree `.git` file, `.venv` paths, `origin`, symlinks) so code run "in the copy" changes the original: high
- Text anyone can write (issue titles, repo files, agent output) passed to an agent that holds the owner's credentials, with no "data, never instructions" rule and no credential isolation: high
- Folder or key names built by joining parts with a character the parts may contain (`owner-repo`), so two inputs collide: high
- A CLI error path that ends in a Python traceback instead of a one-line message (missing tool, `str.isdigit()` on `²`, a directory where a file is expected, non-UTF-8 names): high
- Porcelain git output (`git diff`, `git log`) parsed or applied without pinning the options the user's config can change: medium
