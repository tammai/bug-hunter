# Windows pickup: 2026-11-09-m-scratch-tickets

Start a Claude Code session on Windows in a clone of this repo, then say: "finish 2026-11-09-m-scratch-tickets from its windows-pickup.md". Everything that can run on macOS has run. What is left needs Windows, then shipping.

## Where it stands (written on macOS, 2026-11-09)

- **Branch:** `2026-11-09-m-scratch-tickets`, pushed, no PR yet. `main` is at `4328dfa` (v0.5.0 released, its record merged).
- **Change:** `docs/sdlc/changes/2026-11-09-m-scratch-tickets.md` (AC-001 to AC-006). State: `.sdlc/state/2026-11-09-m-scratch-tickets.md`, track M, risk high, in **Review**.
- **Built and green on macOS:** all six acceptance tests, and `verify.py` passes (full `uv run pytest`).
- **Reviews run on macOS** (reports in `.sdlc/.work/findings/2026-11-09-m-scratch-tickets/`, git-ignored, so not on your Windows clone; the summary is in the change file's `## Review` once written):
  - Round 1: security FAIL (S1: the seal ran a planted `core.fsmonitor` or filter before refusing; S2: `--skip-worktree` hid edits), code FAIL (H1 caller's ignore files, M1, M2 pipe, L1). All fixed with tests.
  - Round 2: both FAIL on one test gap (R2-1); fixed, plus TK1 (untracked-at-birth files now sealed by content) and TK3 (`core.fsmonitor`, `core.hooksPath`, `filter.*`, `diff.*.textconv` refused in `.git/config`). Fixes made after your typed "one more round".
  - Round 3 (the check of those fixes): security PASS, code PASS. Review's gate is met on macOS; `## Review` is written with the Windows checks marked pending.
- **Deviations logged** in the state file: AC-001 and AC-002 widened after round 1; round-2 fixes. The trust-anchor hook flags criteria changes after Review started; your first message in the Windows session accepts that.
- **Tickets left open:** TK2 (the `.git` digest reads whole files under `.git/modules/*/objects` and `lfs/objects`: cost only).

## What only Windows can check

Set up first: `git switch 2026-11-09-m-scratch-tickets`, `uv sync --frozen`, run from Git Bash. Turn on Windows Developer Mode (or run as admin) so the symlink tests can create links.

1. **The full suite.** `uv run pytest` with no filters. The only failures allowed are the rows in `.sdlc/baseline.md` (17 Windows-only rows). A failure not listed there blocks Review; look at it before assuming it's the environment.
2. **Tests that must run and pass on Windows** (`uv run pytest tests/test_scratch.py tests/test_throwaway.py -v`):
   - `tests/test_scratch.py::test_clean_removes_a_junction_without_entering_it` must be **run, not skipped**. It is the only test of the Windows junction handling, and it has never run.
   - `tests/test_scratch.py::test_windows_clean_ignores_a_top_level_file_that_vanishes` (AC-006).
   - Every new seal test in `tests/test_throwaway.py` (AC-001, AC-002). The pipe test skips on Windows (no `mkfifo`), as do the POSIX permission tests.
3. **Things in the seal most likely to differ on Windows.** If a seal test fails here, find out which of these it is before changing code:
   - `core.excludesFile` and `core.attributesFile` pinned to `nul` (`os.devnull`): git must read that as empty. If a base made under one `XDG_CONFIG_HOME` is refused under another, this is why.
   - `core.autocrlf true` in the global config: make a base from a repo that has an uncommitted change and LF files, then `--base` copy it. The copy must succeed (the seal records the status the base had when made).
   - The fsmonitor and filter tests use `touch <marker>` as the planted command. They need `touch` on the Git Bash PATH; if it isn't found the marker isn't created and the test would pass for the wrong reason, so check the marker command ran in a control case.
   - Reading every file under `.git` (the files digest) while git holds a file open; a refusal with "changed after it was made" on an untouched base is the symptom.
4. **Manual check for AC-003** (its test is POSIX-only): with a run folder whose `.bug-hunter-run` is a directory, and again with no marker, `python scripts/isolate.py <scratch> --cache <run>/cache` prints one `error:` line and exits 1, no traceback.
5. **AC-006 for real (optional):** delete a top-level file in a run folder while `python scripts/scratch.py clean <run>` runs; it must not report the vanished file as an error. Hard to time; the unit test covers the code path.
6. **Still true on Windows, don't try to fix:** a folder swapped for a junction *while* `clean` runs is not guarded (AC-006 of lean scratch, narrowed on purpose; `shutil.rmtree` works by path). T6 (deep trees) doesn't apply: Windows uses a different removal path.

Record what you find under `## Review` → "Drift and manual checks" in the change file (a line per item: ran, result). A real bug: failing test first, fix, rerun the suite.

## Then finish

1. Review: `## Review` is already written. Replace its "Pending, needs Windows" bullet with what you ran and found, then `state.py advance 2026-11-09-m-scratch-tickets 4 --gate pass --verified` as a call of its own. A Windows failure that shows a real bug goes back to Build (failing test first), and Review reruns.
2. Ship: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/ship.py" 2026-11-09-m-scratch-tickets ...`, commit, push, `gh pr create`, watch CI (Ubuntu).
3. Merging and the release are the owner's calls. This fixes bugs in v0.5.0 behaviour, so a patch release `v0.5.1` fits the runbook (`knowledge/runbooks/release.md`); decide whether to cut it. The `Bash(gh pr merge *)` allow rule lives in the Mac's git-ignored `.claude/settings.local.json`, not in this repo.
