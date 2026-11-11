# Changelog

## Unreleased

### Changed

- **Shared contracts 1.2.0**, vendored byte-identical in `contracts/v1/` from product-rebuild. C3's level 1 now needs a SUPPORTED verdict, and an `[inferred]` criterion never reaches it by audit; no field or format changes, so findings and the scripts that read specs are unaffected ([change](docs/sdlc/changes/2026-11-11-s-contracts-1-2-0.md)).

## 0.5.0 — 2026-11-09

A multi-agent `/hunt` on a large repo left 18 GB of working files. A run now costs about one clone, one download cache and what each agent installs, and cleans up after itself ([change](docs/sdlc/changes/2026-11-07-l-lean-scratch.md)).

### Added

- **One run folder per run.** `scripts/scratch.py new` makes `<temp>/bug-hunter-XXXX` (mode 0700, marked), with a `cache/` and a `base/`. `/hunt` and `/audit` tell you what they are cleaning up and how much space it freed.
- **`scratch.py clean` and `sweep`.** `clean` removes a run, including read-only trees such as Go's module cache, and refuses anything that is not a folder it made. `sweep` removes leftovers of earlier runs (older than 12 hours by default) and lists younger ones as "may be in use"; both commands run it before the cost question. On Linux and macOS a clean never follows a link swapped in while it runs.
- **`throwaway.py --base <run>/base`** copies the run's one base clone with copy-on-write (`cp -c` on macOS, `--reflink=auto` on Linux, a plain copy elsewhere), and refuses a base it did not make for the same repo.
- **`isolate.py --cache <run>/cache`** shares the download caches of npm, pnpm, Yarn, uv, pip, Poetry, Composer, Go and Bundler across a run's agents. pnpm and uv clone or copy out of it, never hardlink.

### Changed

- **`/hunt` no longer writes drafts on its own.** After verifying it shows the table and asks "Fix these here, or save them as drafts to post?". Only a save writes into the drafts folder, so `/hunt-post` works as before on saved drafts. Unsaved drafts are lost when the session ends, and only saved drafts feed the known list. The drafts folder layout and the draft format are unchanged. With `--format finding-v1` nothing is asked.
- `throwaway.py` clones with `--depth 1`, so code under test that reads its own git history sees one commit.
- Each hunter, verifier and auditor removes its own `copy/` and `home/` before its final reply, and `reap.py` runs before every clean.
- Cargo, Bun, Gradle and Maven keep per-agent caches.

### Known issues

- On Windows, a folder swapped for a junction while `clean` runs is not guarded (`shutil.rmtree` works by path there). Junctions present before the clean are removed without being entered. The Windows-only tests are not run in CI.
- Review tickets left open: the base is writable and only its links are re-checked; a base's `.git` can point git elsewhere through text, not links; the `--cache` marker check can raise; a tree deeper than about 256 levels is left with an error (the marker stays, so a sweep finds it).

## 0.4.0 — 2026-11-09

bug-hunter for rebuilds: a hunt judged against the spec and a running reference, browser repros, and routable findings ([spec](docs/specs/rebuild-upgrade/04-bug-hunter.md), parts 1–5). Every new behaviour is behind a flag: without `--format finding-v1`, `--oracle`, `--reference`, `--browser`, `--yes`, `--budget` or `--cost-log`, `/hunt` behaves as in 0.3.3. Change records: [part 1](docs/sdlc/changes/2026-11-08-m-finding-v1-budget.md), [part 2](docs/sdlc/changes/2026-11-08-m-oracle-scoping.md), [part 3](docs/sdlc/changes/2026-11-08-m-reference-classify.md), [review follow-ups](docs/sdlc/changes/2026-11-08-m-review-followups.md), [part 4](docs/sdlc/changes/2026-11-08-m-browser-mode.md), [part 5](docs/sdlc/changes/2026-11-08-m-departures.md).

### Added

- **Shared contracts v1.** Contracts 1.1.1 vendored byte-identical in `contracts/v1/`, with a test that runs `vendor-check`.
- **`/hunt --format finding-v1 --out <dir>`** writes each verified bug as a contracts C6 finding (`BH-NNNN.json`, `scripts/finding_v1.py`) instead of a draft. A local repro uses bug-hunter's own `cli` shape (README).
- **`/hunt --yes --budget <tokens>`** runs without the cost question when an orchestrator approved a budget, starting hunters only while their worst case fits.
- **`/hunt --cost-log <file>`** appends one contracts C7 line per hunter and verifier (`scripts/cost_log.py`).
- **`/hunt --oracle <spec>`** hunts a rebuild against its spec: one part per feature (story, cited `domain.md` rules, operations, source files from the sdlc records), riskiest first (criteria below level 2, changed lines, failure modes), with Expected citing a criterion or rule and uncovered bugs kept as spec-gap candidates (`scripts/oracle.py`, `drafts.py check --oracle`, `finding_v1.py write --oracle`).
- **`/hunt --target <rebuild> --reference <reference> --format finding-v1`** checks a rebuild against its running reference. The proxy serves both, each on its own loopback listener (`$BASE`, `$REF_BASE`), masking both targets' logins and addresses on each, with one request budget. Hunters and verifiers run every repro against both. The repro is a contracts C4 HTTP replay that `finding_v1.py replay` runs against one base. `finding_v1.py classify` sets each finding's class from the two results by script: `build-defect`, `reference-defect`, `spec-gap`, `accepted-departure`, `environment` or `flaky`. A `Defect: yes` line, confirmed by the verifier, marks behaviour that is wrong on its own. `drafts.py check --reference` also hides the reference's host and logins.
- **`departures.yaml` is read with `--oracle`** (contracts C5). A finding is `accepted-departure` (route `drop`, with the departure ID) when a decided entry in its scope (`criteria`, else `features`) has an `http` match item on the pointer of the repro's last check whose rule the rebuild's value satisfies, the reference doesn't fail the same way and the draft has no `Defect: yes`. An invalid or linked registry stops the run; a proposed entry is a warning and is never matched. bug-hunter never writes the registry; it proposes a departure in a finding (`propose_departure`).
- **`/hunt --target <name> --browser`** hunts UI parts in a real browser. Each bug is proven as one Playwright test, run with the repo's own locked `@playwright/test` through the proxy (`scripts/browser.py run`, never `npx`).
  - `scope.py --live --browser` reports whether browser mode is available and why not (`browser.py detect`), and gives UI parts the new `edge-inputs/web-ui.md` list.
  - `isolate.py --browser` keeps the installed browsers readable and turns off downloads.
  - finding-v1 takes a `{"runner": "playwright", "test": …}` repro, classified like an HTTP one under `--reference`.
- Fixtures: a rebuild + reference pair in `tests/fixtures/reference-pair/` (planted build defect, shared reference defect, departure, spec gap) and a browser app with a planted double-submit bug in `tests/fixtures/browser-app/`.

### Changed

- **The proxy marks its own refusals.** Every refusal `live_proxy.py` answers itself (400, 403, 411, 429, 502, and http.server's own 414, 431 and 501) carries `X-Bug-Hunter-Refused: 1`, and the same header from a target is dropped, so a replay tells "not run" apart from the target's own error.
- **The proxy serves an absolute-form request to its own listener**, which is how a browser talks to its proxy, and logs a refused one to another origin.
- **A verified finding whose fresh replay passes is `flaky`** (routed to the orchestrator), never dropped.
- **`--reference` must be another origin.** The same scheme, host and port as `--target` is refused even with a different base path.
- **`finding_v1.py write --target <name> --ref-target <name>`** refuses a finding whose results or draft show either target's host or a login, the same check drafts get.

### Fixed

- **`oracle.py scope --live`** keeps only features whose files define HTTP routes, and exits 1 when none do, as `scope.py --live` does.
- **`oracle.py` reads no spec or repo file through a symlink**, so a hunted repo can't bring a file from outside it into a hunter's brief.
- **A Python standard-library server is found by `--live`.** A `BaseHTTPRequestHandler` subclass with a `do_GET`/`do_POST`/… method counts as serving HTTP routes, so `/hunt --target` hunts it; a `do_` method on any other class doesn't. Found preparing the live run ([change record](docs/sdlc/changes/2026-11-09-s-release-rc1.md)).
- **A reproduced draft was dropped when a login value is a common word.** `drafts.py check` refused any draft that mentioned a login piece of 6 or more characters, so with an account sent as `Authorization: Bearer member`, every draft saying "member" failed with "holds a login value of account member", and a real finding was lost (found in the 0.4.0-rc.1 smoke test, S-51). A word-like piece (lowercase or Capitalized letters with up to 3 trailing digits, 6–15 characters) now counts only as a credential: after an auth scheme (`Bearer member`), or after a field or flag whose name holds the account's header or cookie name or a credential word (`access_token`, `--password`, `X-Auth-Token`, `"newPassword":`). The full header value and any secret-looking piece, mixed-case tokens included, still count anywhere. The proxy's response masking is unchanged. [Change record](docs/sdlc/changes/2026-11-09-s-login-word.md).

### Removed

- **`finding_v1.py --departure <ID>`**, an unreleased stand-in from part 3: the ID comes from `departures.yaml`.

### Known issues

- **Windows:** 17 tests fail on Windows only (`.sdlc/baseline.md`); none is on the `/hunt` or `/audit` command path. Linux CI is the reference. A symlink test skips on Windows accounts that can't create links.
- **Departure matching** reads the rebuild's value back from the contracts' failure message, so it depends on that wording (with `replay`'s use of contracts' private runner, ticket S2-7); a message cut at 500 characters never matches, and browser, cli and maestro repros are never matched (human-only).
- **No live `--oracle --reference` run yet.** The rebuild + reference fixture pair is classified correctly in pytest (build defect, reference defect, spec gap, accepted departure), but a live `/hunt --oracle --reference` with real agents was skipped for this release by the owner's decision; the first one will be on the owner's first real rebuild.
- **Browser mode with `--oracle`** isn't applied yet (`oracle.py` has no `--browser`); `/hunt` says so.
- **Leak check for word-like logins (S-51 tickets, `docs/sdlc/todo.md`):** a word with a second word between field and value is missed (`<input name="password" value="member">`, `{"name":"token","value":"member"}`, `the password is member`); a lowercase-only random token of 6–15 letters counts only in credential context; and rare prose is still refused, the safe side (`Auth: member`, `a bearer member` for a Bearer account).
- **Review tickets** are listed in each part's change file and in `docs/sdlc/todo.md`: the `oracle.py` citation and scope edge cases, the leak scan's known limits (a protocol-relative `//plainname`, rare address spellings), an allow-list of forwarded headers, and test-suite tidy-ups.

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
