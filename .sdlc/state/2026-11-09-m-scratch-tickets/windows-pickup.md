# Back to macOS: 2026-11-09-m-scratch-tickets

The Windows session ran on 2026-11-11 and handed the feature back. On the Mac, pull the branch, then say: "finish 2026-11-09-m-scratch-tickets from its windows-pickup.md". This file replaced the Windows pickup note; the original is in git history (`648fd0e`).

## What the Windows session did

- Ran every Windows check from the pickup note. Results are in the change file, `## Review` → "Drift and manual checks" → "Windows run, 2026-11-11".
- **Found and fixed one real bug in the seal** (`scripts/throwaway.py`):
  - What happened: an edit to a tracked file in the base after it was made was not refused on Windows.
  - Cause: status names a path, not what it holds, and a file already non-clean at birth stays ` M` after another edit. On Windows every text file is non-clean at birth (the clone checks out with the system `core.autocrlf=true`, which the pinned status hides). On every platform, so is every file the owner's uncommitted changes touched.
  - The fix: `_seal_git` hashes the contents of every path the pinned status lists (changed, deleted as a sentinel, untracked, ignored), with status and the index flags read once.
  - The test: `test_a_file_that_was_changed_in_the_base_at_birth_is_sealed_by_content`, red then green on Windows; it should also fail on `main`'s seal on any OS.
- The feature went back to Build (`state.py advance … 2`). Deviations are logged for the fix and for the baseline.
- `.sdlc/baseline.md` grew by three Windows-only rows with the owner's OK. All three fail identically on `main`. One of them is a real v0.5.0 bug, filed in `docs/sdlc/todo.md`: `scratch.py clean` can't remove a read-only folder on Windows.

## What's left, on the Mac

1. **Acceptance tests table:** add `test_a_file_that_was_changed_in_the_base_at_birth_is_sealed_by_content` to AC-001's row in `## Acceptance tests`. It changes the record above `## Review`, so the trust anchor will ask for a typed OK. Then `verify.py red` can't re-record AC-001 (its other tests pass), so decide with the owner how the red evidence stands: the new test was seen red on Windows, as `## Review` says.
2. **`verify.py --feature 2026-11-09-m-scratch-tickets`:** must pass. The red records for AC-001 to AC-006 are in the Mac's `.sdlc/.work/`.
3. **Review round on the seal change:** `state.py advance … 3 --gate pass --verified`, then a security and code round (high risk) on `git diff 648fd0e -- scripts/throwaway.py tests/test_throwaway.py`, told it follows round 3. Check especially:
   - the porcelain `-z` parsing in `_status_paths` (renames carry a second path);
   - the cost: on Windows every copy now reads every text file of the base (like TK2);
   - that bases made before this change are refused as changed (they are throwaway; "make a new base").
4. **Update `## Review`** with the round, then Ship as the original note said: `ship.py`, PR, watch CI (Ubuntu). Merging, and whether to cut v0.5.1, are the owner's calls.
