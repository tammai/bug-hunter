# Recurring defects

One line per defect: what it looks like, then the severity.

- A record of an outside action (an issue filed, a message sent) written after the action with no write check beforehand, no fsync and no fallback, so a failed write repeats the action next run: high
- A target repo copied with `cp -R` (worktree `.git` file, `.venv` paths, `origin`, symlinks) so code run "in the copy" changes the original: high
- Text anyone can write (issue titles, repo files, agent output) passed to an agent that holds the owner's credentials, with no "data, never instructions" rule and no credential isolation: high
- Folder or key names built by joining parts with a character the parts may contain (`owner-repo`), so two inputs collide: high
- A CLI error path that ends in a Python traceback instead of a one-line message (missing tool, `str.isdigit()` on `²`, a directory where a file is expected, non-UTF-8 names): high
- Porcelain git output (`git diff`, `git log`) parsed or applied without pinning the options the user's config can change: medium
- A shell step built from a name the target controls (a folder, a file) and quoted with double quotes, or not filtered for quotes, `$`, backticks, backslashes and a leading `-`: high
- Agent isolation done by moving `HOME` only, missing variables already expanded to the real home, Java's `user.home`, JVM option variables and active virtualenvs: high
- `eval "$(cmd)"` used for a safety setup step, so a failed or empty `cmd` runs the rest unprotected: high
- A tool setting kept pointed at the owner's real folders (runtime managers, SDKs) while the tool can auto-install into them from a repo file: high
- Deciding "is this a secret?" from the shape of free text (`NAME = value`, long base64) instead of checking against the values actually found: high (it trades leaks for rejected findings each way it is tuned)
- A placeholder or redaction test that matches a substring, so a partly masked real value (`Pass<redacted>`, `AKIA…xxxx`) counts as a placeholder: high
- A "looks like a path" or "looks like code" exemption that also matches real secret alphabets (base64 values starting with `/`, JWTs with dots): high
- A multi-line block parser (PEM body) that enters block mode on a header mention, or never leaves it, so the rest of the file is skipped: high
