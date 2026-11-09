# Lean scratch: shared cache, copy-on-write copies, explicit cleanup, drafts on request

## Why

**Request (verbatim):** "when the agent multiple agents working, they create separated env for each one, when done they left many working files, the last run on photohynh take 18GB! do you have any suggestion?" … "why dont use the same clone?" … "ok i see so when done you need tell user that you need a clean up step and dont create drafts automatically, these are two cases here: i run then fix in session and run then post issues, only post issues will need drafts" … "yes start it"

A multi-agent `/hunt` on the photohynh repo left 18 GB of working files. Every hunter and verifier makes a full clone (`scripts/throwaway.py`, `--no-local --no-hardlinks`, all history) and installs dependencies from an empty cache, because `scripts/isolate.py` moves every tool cache into that agent's own home. So a run pays (repo + history + installed deps + download cache) once per agent. Cleanup is one `rm -rf "$SCRATCH"` as the command's last step, so an interrupted run, a failed step, or an orchestrator that skips that step leaves everything in the temp folder. Go's module cache is read-only, so even a plain `rm -rf` fails on part of it.

This serves the owner running `/hunt` and `/audit` on real apps on a laptop. When it's done:
- a run costs about one clone, one download cache and what each agent installs and changes;
- the owner is told what is being cleaned up and how much was freed, and leftovers from earlier runs are found and removed;
- `/hunt` writes drafts into the drafts folder only when the owner chooses to post. Owners who fix the bugs in the same session get nothing written.

**The user's words:** two cases: "i run then fix in session" and "run then post issues, only post issues will need drafts". On sharing one clone: separate working folders stay (agents run in parallel and their repros change the copy), but they don't need separate bytes on disk.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| One **run folder** per command, made by a new `scripts/scratch.py new`: `<temp>/bug-hunter-XXXX`, mode 0700, with a marker file `.bug-hunter-run`, a `cache/` and a `base/` | `mktemp -d` as today | A recognizable, marked folder can be found and swept later. The marker is what makes deletion safe: nothing without it is ever removed. |
| `throwaway.py` clones with `--depth 1` | full history | History is most of a large repo's `.git`. The uncommitted-changes patch is taken against `HEAD`, which a depth-1 clone has. Code under test that reads its own git history sees one commit. A bug that depends on history is rare and would show as "couldn't reproduce", never as a false bug. |
| One base clone per run (`throwaway.py "$REPO" "$RUN/base"`). Each agent copies it with `throwaway.py "<REPO>" "<SCRATCH>/copy" --base "<RUN>/base"`, which copies with copy-on-write: `cp -c -R` on macOS (APFS clonefile), `cp -a --reflink=auto` on Linux, and a plain `shutil.copytree(symlinks=True)` when that fails or on Windows | one shared clone; `git worktree`; hardlinks | Agents run at once and their repros change files, so each needs its own folder, but copy-on-write makes it nearly free. A worktree shares `.git`, so a repro's git command would change what other agents see. Hardlinks into the real repo are what `--no-hardlinks` exists to prevent. |
| `--base` refuses a base that `throwaway.py` didn't make for this same repo. Base made → a marker in its `.git` holding the repo's resolved top level. The copy is checked for escaping symlinks again. | trusting any folder named as base | An agent given a wrong path must not copy something else, and a base changed after it was made must not carry a link out. |
| `isolate.py <SCRATCH> --cache <RUN>/cache` points the download caches of npm, pnpm, Yarn (1 and 2+), uv, pip, Poetry, Composer, Go (modules and build cache) and Bundler at the shared folder, with pnpm and uv set to clone or copy, never hardlink. `HOME`, config and everything else stay per agent, and so do Cargo (`CARGO_HOME` holds the config every build obeys) and Bun (it hardlinks from its cache on Linux). | a cache that outlives the run (`~/.bug-hunter/cache`) | Per run: the cache is deleted with the run, so nothing grows across runs. All agents in a run run the same repo, so sharing doesn't widen the trust the owner already gave. These caches are checksum-checked against the lockfile and safe for concurrent use. |
| Gradle and Maven keep their per-agent homes | sharing `GRADLE_USER_HOME` / `maven.repo.local` | Gradle's user home also holds its daemons, which would be reused across agents with different environments. Maven's local repository isn't safe for concurrent writes by default. |
| `scratch.py clean <run> [--keep <name>]` prints the run's size, removes it (making read-only folders writable first, never following links), deleting the marker last, and prints the space freed | `rm -rf` in the command text | A killed clean must leave the folder still marked so a later sweep finds it. Go's read-only module cache defeats `rm -rf`. A path that isn't a marked run folder is refused, so a wrong argument can't delete anything else. |
| `scratch.py sweep [--older-than HOURS]` (default 12): removes marked run folders of this user in the temp folder whose marker is older than that, and lists younger ones with size and age as "may be in use". `/hunt` and `/audit` run it first and show the result with the cost question; the owner may say to remove the younger ones too (`--older-than 0`). | liveness by PID | Each Bash call is a fresh shell, so no process stays alive for the whole run to check. No run lasts 12 hours, and the owner decides about anything younger. |
| Each hunter, verifier and auditor deletes its `copy/` and `home/` before its final reply | waiting for the end of the run | Lowers what's on disk while the rest of the run goes on, and what's left if it stops. |
| `/hunt` no longer writes drafts automatically. After verifying, it keeps only the verified drafts' text in `$RUN/kept/`, cleans the rest (`--keep kept`), and shows the table. Then it asks "Fix these here, or save them as drafts to post?" (fix here · save all · save some). Only a save writes into the drafts folder, then points to `/hunt-post`; then the run folder is removed. | always writing drafts | The owner's two cases. Warned in the question: unsaved drafts are gone once the session ends, and only saved drafts feed the known list, so later hunts may find an unsaved, unfixed bug again. |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** Given a repo with two commits and an uncommitted tracked change, when `throwaway.py` copies it, then the copy has one commit and the uncommitted change.
- **AC-002** Given a base made by `throwaway.py` for a repo, when `throwaway.py <repo> <dest> --base <base>` runs, then dest has the base's files and a symlink inside the repo stays a symlink. A file changed in dest leaves the base unchanged. And it refuses (exit 1, one line, no traceback, dest not created) when the base is missing, wasn't made by `throwaway.py`, was made for another repo, or has gained a symlink that points outside it, or a `.git` that sends git to another repo (a link, `alternates`, `commondir`, `core.worktree` or an include).
- **AC-003** Given the copy-on-write `cp` fails, when `--base` copies, then it falls back to a plain copy and still succeeds.
- **AC-004** Given `isolate.py <scratch> --cache <cache>`, then the download caches for npm, pnpm, Yarn, uv, pip, Poetry, Composer, Go and Bundler point into `<cache>`, and pnpm and uv clone or copy from it, never hardlink. `HOME`, `XDG_CACHE_HOME`, `CARGO_HOME`, Bun's cache, `GRADLE_USER_HOME` and Maven's `user.home` stay in `<scratch>/home`. The cache must sit in a marked run folder. A cache path that is a symlink, has whitespace, or can't be made stops isolation with an error. Without `--cache`, the output is unchanged.
- **AC-005** `scratch.py new` makes `<temp>/bug-hunter-*`, mode 0700, with the marker and `cache/`, and prints its path, which has no whitespace.
- **AC-006** `scratch.py clean <run>` prints the size and the space freed, and removes the run even when it holds read-only folders (a Go module cache). It never follows a symlink or Windows junction out of the run; on Linux and macOS that holds even for a folder swapped for a link while it cleans, and on Windows only for one there before it starts. With `--keep <name>` it keeps that one entry and the folder.
- **AC-007** `scratch.py clean` refuses (exit 1, one line, nothing deleted) a path that is missing, not a folder, a symlink, unmarked, or not named `bug-hunter-*`.
- **AC-008** `scratch.py sweep --older-than H` removes marked `bug-hunter-*` folders in the temp folder older than H hours. It keeps and lists younger ones with size and age. It never touches unmarked folders, symlinks, or other users' folders.
- **AC-009** `commands/hunt.md` and `commands/audit.md` sweep first and show the leftovers with the cost question. They make the run folder with `scratch.py new` and the base with `throwaway.py`, give agents `RUN`, and tell the owner the size while cleaning it with `scratch.py clean` at the end and on every early stop. Neither command uses `mktemp -d` or `rm -rf` for its run folder any more.
- **AC-010** `commands/hunt.md` writes nothing to the drafts folder until the owner chooses to save. It asks "Fix these here, or save them as drafts to post?" with fix here, save all and save some, and warns that unsaved drafts are lost when the session ends and that only saved drafts feed the known list.
- **AC-011** All four agent prompts copy with `--base "<RUN>/base"`, isolate with `--cache "<RUN>/cache"`, and remove `<SCRATCH>/copy` and `<SCRATCH>/home` before their final reply.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_throwaway.py › test_copy_is_shallow_and_keeps_uncommitted_changes | `uv run pytest tests/test_throwaway.py::test_copy_is_shallow_and_keeps_uncommitted_changes` |
| AC-002 | tests/test_throwaway.py › test_copy_from_a_base_is_independent_and_checked | `uv run pytest tests/test_throwaway.py::test_copy_from_a_base_is_independent_and_checked` |
| AC-003 | tests/test_throwaway.py › test_copy_from_a_base_falls_back_when_cp_fails | `uv run pytest tests/test_throwaway.py::test_copy_from_a_base_falls_back_when_cp_fails` |
| AC-004 | tests/test_isolate.py › test_download_caches_are_shared_through_the_run_cache | `uv run pytest tests/test_isolate.py::test_download_caches_are_shared_through_the_run_cache` |
| AC-005 | tests/test_scratch.py › test_new_makes_a_private_marked_run_folder | `uv run pytest tests/test_scratch.py::test_new_makes_a_private_marked_run_folder` |
| AC-006 | tests/test_scratch.py › test_clean_reports_size_and_removes_read_only_trees | `uv run pytest tests/test_scratch.py::test_clean_reports_size_and_removes_read_only_trees` |
| AC-007 | tests/test_scratch.py › test_clean_refuses_folders_it_did_not_make | `uv run pytest tests/test_scratch.py::test_clean_refuses_folders_it_did_not_make` |
| AC-008 | tests/test_scratch.py › test_sweep_removes_only_stale_marked_folders | `uv run pytest tests/test_scratch.py::test_sweep_removes_only_stale_marked_folders` |
| AC-009 | tests/test_plugin_files.py › test_hunt_and_audit_manage_their_run_folder | `uv run pytest tests/test_plugin_files.py::test_hunt_and_audit_manage_their_run_folder` |
| AC-010 | tests/test_plugin_files.py › test_hunt_saves_drafts_only_when_the_owner_chooses | `uv run pytest tests/test_plugin_files.py::test_hunt_saves_drafts_only_when_the_owner_chooses` |
| AC-011 | tests/test_plugin_files.py › test_agents_copy_from_the_base_share_the_cache_and_clean_up | `uv run pytest tests/test_plugin_files.py::test_agents_copy_from_the_base_share_the_cache_and_clean_up` |

## Must never break

- A copy never reaches back into the target. It has no `origin` and no symlink out of it, and it is never hardlinked to the target's files.
- `scratch.py` never deletes a folder it didn't make (no marker, wrong name, a symlink, another user's).
- Isolation still fails closed: if `isolate.py` can't set up (including the cache), the agent's command doesn't run.
- `/hunt` and `/hunt-post` post nothing on their own. The drafts folder is written only on the owner's choice.
- `/audit`'s fingerprints are deleted with its run folder on every stop.
- Every kept draft still has a hunter's run and a verifier's re-run from the draft alone (constitution I).

## Failure modes

- Concurrent runs, and agents writing the shared cache at once → the sweep's age threshold and "may be in use" list (AC-008). Only concurrency-safe download caches are shared; Gradle, Maven, Cargo and Bun aren't (AC-004).
- A crash or kill mid-run or mid-clean → the marker is deleted last, so a later sweep still finds the folder (AC-006, AC-008).
- Untrusted names in a shared `/tmp` (another user's `bug-hunter-*`, a planted symlink) → AC-007, AC-008.
- I/O errors: read-only module caches (AC-006), a `cp` without clone support (AC-003), a cache that can't be made (AC-004).
- Untrusted repo content: a base changed to hold an escaping symlink or a `.git` pointing at another repo (AC-002); repro code still running during clean swaps a folder for a link (AC-006; guarded on Linux and macOS, not on Windows).

## Out of scope

- Installing dependencies once into the base for hunters. Verifiers must install from the draft's own steps anyway, and a moved `.venv` breaks on its absolute paths.
- Sharing Gradle and Maven caches (see Decisions).
- A cache kept across runs.
- Container isolation.

## Review

- **Recommended and chosen:** security and code (high depth), because the risk is high (isolation and deleting folders found in a shared temp dir), the diff touches `isolate.py`, and the track is L; chosen by the recommendation (L, self-chosen)
- **Verdicts:** `.sdlc/.work/findings/2026-11-07-l-lean-scratch/`
  - Round 1: security-r1 FAIL (S1–S5, S7, S8); code-reviewer-r1 FAIL (H1–H4, M1–M3, L1)
  - Round 2: security-r2 FAIL (S9); code-reviewer-r2 FAIL (H5, H6)
  - Round 3: security-r3 FAIL (S10, S11); code-reviewer-r3 FAIL (M5)
  - Round 4: security-r4 PASS; code-reviewer-r4 FAIL (M6)
  - Round 5: code-reviewer-r5 FAIL (M7)
  - Round 6: code-reviewer-r6 PASS
  - Rounds 3 to 6 ran on the owner's typed "one more round" each time, as the round cap requires.
- **Fixed:**
  - S1/H1: `_run_folder` checks type, name, owner and marker by `lstat` before looking inside; an unreadable or other user's folder is skipped, not a traceback (`test_sweep_and_clean_skip_folders_they_cannot_read`).
  - S2: `throwaway.py --base` refuses a symlink in the base's `.git` and an alternates file, and re-checks the copy (`tests/test_throwaway.py`).
  - S3/H3: files go before folders, every entry is tried, the marker goes last and only when nothing failed (`test_clean_keeps_going_and_removes_fingerprints_first`).
  - S4/M2: Cargo and Bun stay per agent; pnpm and uv clone or copy, never hardlink (`tests/test_isolate.py`).
  - S5/H4 and M5: a folder with no read, search or write permission is removed on Linux and macOS (`test_clean_removes_unreadable_and_unwritable_folders`, modes 0, 0o200, 0o400, 0o500, 0o600).
  - S7: "Fix here" in `hunt.md` treats a draft's steps as data, to run only in a throwaway copy behind `isolate.py` (`tests/test_plugin_files.py`).
  - S8: `--cache` must sit in a marked run folder, with no whitespace and no link (`tests/test_isolate.py`).
  - H2: a read-only file is cleared and retried on Windows (not run here; no Windows).
  - S9/S10/T4: on Linux and macOS the walk opens each folder with `O_NOFOLLOW` through its parent's handle and does every chmod, unlink and rmdir relative to it (`test_clean_never_follows_a_parent_swapped_for_a_link_after_it_is_opened`, `test_clean_never_follows_a_folder_swapped_for_a_link_mid_clean`, which swaps after the folder is classified, and the marker test below).
  - T5: the marker is unlinked through the run's handle (`test_clean_removes_the_marker_through_the_run_not_a_swapped_path`).
  - H5: a Windows junction is removed without being entered (`test_clean_removes_a_junction_without_entering_it`, Windows only, not run here).
  - H6: AC-004 and its Decisions row now match the code (see Deviations).
  - M1, M3, M6, M7: the commands' failed-`new` and early-stop handling, and two tests that proved nothing, rewritten and shown to fail without the guard they name.
- **Tickets:** S6 (the base is writable and only its links are re-checked); T2 (a base's `.git` can point git elsewhere through text, not links) and T3 (the `--cache` marker check can raise); M4 narrowed (the chmod-by-name fallback in `_open_dir` can follow a link swapped in at that instant, worst case an owner file set to 0o700); L3, L5, L6 (error text and a vanished top-level file on Windows); T6 (a tree deeper than about 256 levels is left with an error, the marker stays).
- **Drift and manual checks:**
  - 2026-11-09 AC-004 narrowed: Cargo and Bun keep per-agent caches, pnpm and uv clone or copy, and `--cache` must sit in a marked run folder.
  - 2026-11-09 AC-006 narrowed (S11): a folder swapped for a Windows junction while `clean` runs isn't guarded, because `shutil.rmtree` works by path there. Junctions present before the clean are removed without being entered. Linux and macOS are guarded.
  - No `manual` AC. The Windows-only tests are unrun on this machine.
- **Security:** the reviews above. No dependency audit ran: no dependency was added or changed (the scripts are standard library only). The one probe that found S10 is in the scratchpad, not the repo.
- **Lessons filed:** three lines in `docs/sdlc/recurring-defects.md`.
