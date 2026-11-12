# Windows pickup: 2026-11-12-m-windows-seal-and-clean

Built, reviewed and shipped as a PR from macOS on 2026-11-12. One check is left, and it needs Windows: AC-004 in `docs/sdlc/changes/2026-11-12-m-windows-seal-and-clean.md`. On Windows, check out the PR branch, then say: "run the Windows check of 2026-11-12-m-windows-seal-and-clean from its windows-pickup.md".

## The check

1. `uv sync --frozen`, then `uv run pytest`.
   - Expected: `tests/test_scratch.py › test_clean_reports_size_and_removes_read_only_trees` now **passes**.
   - Every other failure must be a row of `.sdlc/baseline.md`.
2. A base on Windows, with Git for Windows' system `core.autocrlf=true`:
   - Make a repo with a few committed text files, then run `python3 scripts/throwaway.py <repo> <run>/base`.
   - `git -C <run>/base config --local --get core.autocrlf` prints `true`.
   - Pinned status is empty: `GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=nul git --no-optional-locks -C <run>/base status --porcelain` prints nothing.
   - Run a plain `git -C <run>/base status` (this refreshes the index), then `python3 scripts/throwaway.py <repo> <run>/copy --base <run>/base` exits 0.

## After it passes

- Remove the `test_clean_reports_size_and_removes_read_only_trees` row from `.sdlc/baseline.md`.
- Tick the read-only item in `docs/sdlc/todo.md`.
- Record the run under `## Review` → "Drift and manual checks" → AC-004.
- `state.py log` the result, then commit and push to the PR branch. Merging is the owner's call.

If it fails, record what failed in the same place and stop. Don't change the code on Windows without a failing test first.
