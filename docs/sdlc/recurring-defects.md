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
- Log redaction that matches secret words in raw text without first decoding `%xx` (nested), `\u`, `\x` and `&#` escapes, so `%2574oken` or `password` is logged: high
- A fallback path (malformed input, parse error, a body that was withheld) that logs raw input under a weaker check than the main path: high
- A test's fake CLI (a `#!` script named `gh`) that the OS can't run, so the code under test finds the real, logged-in tool on PATH and acts for real (Windows filed real issues): high
- "Logged out" by pointing a CLI at an empty config folder while the OS keyring (Windows Credential Manager, macOS Keychain) still holds its token; override the token variable instead: high
- A capability check that names `os.replace` (or another alias) in `os.supports_dir_fd`, which only lists `os.rename`, so the safe descriptor path silently turns off and the fallback passes the same tests: high
- On Windows, environment handling built on `os.environ` (names uppercased) feeding a case-sensitive shell, so `unset NAME` misses `Name` and mixed-case secrets survive: high
- A log of request bodies that redacts by text pattern instead of parsing the body's own shape (JSON, ndjson, form, multipart), so secret-named keys with object values, multi-line parts or bracketed names (`user[password]`) leak: high
- Credentials loaded from a config file and sent as HTTP headers without checking them first, so a value with a line break or a non-Latin-1 character raises inside the HTTP library and its traceback prints the token: high
- A proxy that relays a server's responses unchanged to an agent that must not see the credentials it added, so an echoing endpoint (debug page, `Location`) hands them back: high
- A read-only guard that checks only the request method, so `X-HTTP-Method-Override` or `_method` turns an allowed GET into a write: high
- A shell step that sets a variable as a command prefix (`BASE=x curl "$BASE"`), which the same command's own expansion never sees, or that a later setup step unsets (`isolate.py` drops `*AUTH*`): high
- Masking that matches secrets case-insensitively or bare host names inside words, so ordinary response text is mangled and hunters report the proxy's damage as the target's bug: medium
- Stopping a background job by the PID `$!` gave, when `$!` can be a subshell (`cmd && prog &`, `( … ) &`): killing it leaves `prog` running under PID 1; stop the whole process tree, recorded while the subshell lives: high
- A `cd` chained into a backgrounded `&&` list (`cd copy && … & echo $! > f`): the `cd` runs only in the background job, so the next relative write lands in the starting folder (the target repo): high
- `shutil.which` (or any PATH lookup) run from inside a target repo on Windows without `NoDefaultCurrentDirectoryInExePath`: a `ps.bat` the repo commits runs unisolated; a test that removes the variable must match its name case-insensitively: critical
- `Path.resolve()`, `is_file()` or `open()` on a path an agent or target wrote before checking it lies inside the repo: a `\\host\share` path makes Windows authenticate to that host: high
- An error or problem line that echoes the input it rejected, when that input can be a secret (a citation, a header, a config line): name the item by position instead: high
- A numeric field read from an agent- or target-written file with `isdigit()` and `int()` but no length or range bound, so a huge value raises (`OverflowError`, `ValueError`) instead of being skipped: high
- Commands and outputs recovered by parsing free-form markdown (heredocs, fences, prompts, prose) instead of having the producer write them as structured data and rendering the markdown from it: high
