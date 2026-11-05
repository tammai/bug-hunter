---
description: File the bug-hunter drafts you name as GitHub issues, from your own gh login, with a label you choose
argument-hint: <numbers…> [--label <label>]
---

# /hunt-post

File only the drafts the owner names in `$ARGUMENTS`. Nothing else is ever filed, and the filing happens only through `post.py`, which checks each draft's format, checks `gh auth status`, records each filed draft in `posted.json` and never files one twice. Never file an issue, comment or PR any other way.

1. **Find the drafts.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/drafts.py" dir "$PWD"` from the target repo (the one the drafts were hunted in). No numbers in `$ARGUMENTS` → list the drafts there (number and title) and ask which to file; stop.
2. **Pick the label.** Take it from `--label` in `$ARGUMENTS`. None given → ask the owner which label to use (say that on a repo tohe manages, `bug` makes tohe pick the issue up). Never pick one yourself.
3. **Confirm.** Show each named draft's number and title, the label and the repo (`gh repo view --json nameWithOwner -q .nameWithOwner`), and ask the owner to confirm. Anything but a yes → stop.
4. **File.** Run, from the target repo:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post.py" "<drafts dir>" <numbers…> --label "<label>"`
5. **Report** what it printed: each draft's issue URL, or why it was skipped. On a non-zero exit, show its error as is: it filed nothing when a check failed, and kept a record of what it had already filed when `gh` failed part way. Don't retry on your own.
