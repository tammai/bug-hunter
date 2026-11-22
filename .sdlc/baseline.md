# Known failures baseline

<!-- Written by /sdlc:setup (sdlc v3.2.1). Yours from then on: the plugin never overwrites it.
     Review (Stage 3) fails only on failures NOT listed here. Rules:
     - Shrinks on its own: when a listed item passes, the build removes it and says so in the change file's `## Review`.
     - Never grows silently: adding an item needs the user's OK and a Deviations entry in that feature's state.md.
     - Fixing items is its own S-track work, not a side job inside a feature. -->

Recorded: 2026-11-06 at commit bc45a9d, running `uv run pytest` on Windows 11 (Git Bash, uv's Python 3.13); added with the owner's OK in docs/sdlc/changes/2026-11-06-m-windows-isolation.md. Pruned 2026-11-22 in docs/sdlc/changes/2026-11-22-m-windows-suite.md: the other 17 rows pass on the `windows-latest` CI runner (run 45020995450).

Both rows pass on Linux CI and on Windows with Python 3.13+. Neither is on the `/hunt` or `/audit` command path.

## Failing tests

| Package | Test (file › name) | Failure, one line | Since |
|---|---|---|---|
| (root) | tests/test_post.py › test_refuses_odd_numbers_duplicates_and_unusable_record | Skips on Python 3.12 (tempfile retries a refused mkstemp 2^31 times); passes on 3.13+; ticket: post.py hangs on a locked drafts folder on 3.12. | 2026-11-06 |
| (root) | tests/test_post.py › test_shows_url_when_recording_fails_after_filing | Skips on Python 3.12 (tempfile retries a refused mkstemp 2^31 times); passes on 3.13+; ticket: post.py hangs on a locked drafts folder on 3.12. | 2026-11-06 |

## Lint and type errors

Counts per rule and file. Review fails if any count goes **up**, or a rule/file appears that isn't listed.

| Package | Tool | Rule | File | Count |
|---|---|---|---|---|
| — | none | | | |

## Build warnings / other

- none
