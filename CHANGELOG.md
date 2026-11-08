# Changelog

## Unreleased (0.4.0, part 1)

### Added

- **Shared contracts v1.** Contracts 1.1.0 vendored byte-identical in `contracts/v1/`, with a test that runs `vendor-check`.
- **`/hunt --format finding-v1 --out <dir>`** writes each verified bug as a contracts C6 finding (`BH-NNNN.json`, `scripts/finding_v1.py`) instead of a draft. Its `repro` uses bug-hunter's own `cli` shape (README) until the contracts settle one.
- **`/hunt --yes --budget <tokens>`** runs without the cost question when an orchestrator approved a budget, starting hunters only while their worst case fits.
- **`/hunt --cost-log <file>`** appends one contracts C7 line per hunter and verifier (`scripts/cost_log.py`).

## 0.3.3 — 2026-11-08

### Fixed

- **0.3.2: a hunter's fresh-copy re-run fails on Linux.** Since 0.3.2 every agent call starts inside its copy, so the step that deletes and rebuilds the copy ran from a folder that no longer existed, and `throwaway.py`'s `git clone` failed (`getcwd() failed`). `throwaway.py` now runs git from the system temp folder, and takes relative paths as before. Windows (Git Bash) was not affected.

## 0.3.2 — 2026-11-08

First live validation. bug-hunter ran 18 times (`/hunt` on a Python CLI, a Node/TS service and a Go module, `/hunt --target` on a running HTTP service, `/audit` on an Express API), and every defect those runs found in bug-hunter itself is fixed here, each test first. The runs are recorded in [knowledge/runs/](knowledge/runs/); the change record is [docs/sdlc/changes/2026-11-08-m-b0-live-validation.md](docs/sdlc/changes/2026-11-08-m-b0-live-validation.md).

### Fixed

- **`--max` picks the parts that matter.** `/audit` ranks parts by their strongest security keyword (identity and money, then entry points, then data and config), so `--max 2` audits auth code instead of jest config; `author` no longer counts as `auth`. Plain `/hunt` puts parts made only of build or docs tooling (`setup.py`, `*.config.ts`, `docs/`) last.
- **Proven bugs are no longer dropped by the format check.** `drafts.py` and `findings.py` read code blocks as CommonMark does, so a Python traceback's indented `~~~~^^^^` line no longer ends the block.
- **Audit findings must cite real lines in the repo.** `findings.py check --repo` drops a finding whose Where cites a path outside the repo, a missing file or a line past the end; `dedupe --repo` matches absolute and relative citations of the same line. Both decide from the path's text before touching the disk, and name a bad citation by position, never by its text.
- **Drafts can't carry your account name.** `drafts.py check` rejects a draft containing your home folder's path.
- **Servers agents start are stopped.** The isolation prefix records every background job and the processes under it; the new `scripts/reap.py` stops them before `/hunt` and `/audit` delete their scratch folder, including a program started under a subshell (`cmd && prog &`). It never runs a `ps` or `kill` from the target repo's folder.
- **Agents can't write into the target repo by accident.** Every agent call starts inside the agent's own copy.
- **Verifiers vouch only for what they ran.** `repro-verifier` fails a draft that claims a wrong behaviour no step shows; `finding-verifier` rejects a citation whose line holds other code, even one line off.

### Known issues

- **PID reuse (ticket S4):** a PID recorded in `bg.pids` can be reused by an unrelated process of yours before `reap.py` runs, which would then stop it and the processes under it.
- **Cost preview units:** the preview's "about 100k tokens per hunter" matches fresh tokens (input, output, cache writes), not processed tokens, which ran 3–18× higher with cache reads. Per-run cost logging comes in 0.4 (`cost.jsonl`).
- **Linux and macOS:** the new tests (`tests/test_reap.py`, the new cases in `tests/test_isolate.py`, the citation tests in `tests/test_findings.py`) were run only on Windows (Git Bash) before this release; CI on Linux runs them with this tag.
- A live hunt (`--target`) drops a bug the hunter can show only offline; rerun `/hunt` without `--target` to have it verified.

## 0.3.1 and earlier

See the [GitHub releases](https://github.com/tammai/bug-hunter/releases).
