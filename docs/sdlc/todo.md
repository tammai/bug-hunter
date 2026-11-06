# Todo

## Open

- [ ] Make the test suite pass on Windows: the 16 Windows-only failures in `.sdlc/baseline.md` (fake `gh` that Windows can run without passing titles through `cmd.exe`, `USERPROFILE` in the drafts and findings fixtures, POSIX-mode asserts, read-only git objects, CRLF and forbidden names in fixtures, symlink privilege), then add a `windows-latest` CI runner — left out of the Windows isolation change on purpose; 2026-11-06-m-windows-isolation (2026-11-06)
- [ ] Small `isolate.py` follow-ups from the Windows isolation review:
  - match 8.3 short names (needs `GetLongPathNameW`);
  - match a quoted value with a space inside the quotes;
  - give a one-line error instead of a traceback for an unpaired UTF-16 surrogate in a Windows env value, and fix that test's skip reason;
  - drop the extra `lstat` calls in the path fallback;
  - narrow the test guard's PATH filter so it stops hiding Homebrew's other tools on macOS.

  Review tickets (CR5, CR10, R3-1, R3-2, S4). Not bugs on the command path; 2026-11-06-m-windows-isolation (2026-11-06)
- [ ] Decide whether `isolate.py` should also unset inherited `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT` and `GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*`, which can inject git config (a credential helper) without any file — found in the Windows isolation change, not asked for there (2026-11-06)
