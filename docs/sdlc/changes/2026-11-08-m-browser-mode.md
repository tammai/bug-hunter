# bug-hunter 0.4 part 4: browser mode and web-ui edge inputs

## Why

**Request (verbatim):** implement docs/specs/rebuild-upgrade/04-bug-hunter.md, part 4 only.

Part 4 is B3 of [docs/specs/rebuild-upgrade/04-bug-hunter.md](../../specs/rebuild-upgrade/04-bug-hunter.md). Anything that needs a browser is dropped today as "couldn't reproduce". With `/hunt --target <name> --browser`, hunters and verifiers prove UI bugs as one Playwright test file, run with the repo's own locked Playwright, through the proxy. Built on the review follow-ups (branch `2026-11-08-m-review-followups` @ 5c0c8b9).

**The user's words:** orchestrator answers (Orca, msg_af4092430112):
- Q1: a `--browser` flag requiring `--target`. Design rule 5 (README of the rebuild upgrade) says new behaviour comes from an artifact or an explicit flag; B3's "enabled when" is the availability condition. Recorded as a deviation.
- Q2: detection as proposed:
  - a `package.json` lists `@playwright/test` in `devDependencies`;
  - a tracked lockfile beside it (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`) contains it;
  - the browsers folder holds a chromium build. That folder is `PLAYWRIGHT_BROWSERS_PATH`, else the platform default.
  - `scope.py` reports why when any of these fails.
- Q3: browsers are used read-only from the owner's folder:
  - `PLAYWRIGHT_BROWSERS_PATH` and `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` are set;
  - no `playwright install`: a prompt rule, plus a guard if one is cheap;
  - documented beside the isolation notes.
- Q4: the proxy is the browser's only origin:
  - an absolute-form request is accepted only to the listener itself, and CONNECT is refused;
  - the browser runs with loopback bypass off;
  - a wrapper config sets this up, and the test never runs through `npx`.
- Q5: the test reads `ACCEPT_BASE_URL` and `ACCEPT_ACCOUNT_<NAME>`, the C4 names, not B3's `BASE`/`REF_BASE`; a deviation. With `--reference`, each side's run sets `ACCEPT_BASE_URL`.
- Q6: a fixture app plus pytest as proposed. The live acceptance run is pre-approved at a hard cap of USD 8 (`--max-budget-usd`), with network allowed for `npm ci`.
- Q7: risk is high, so plan approval goes to the orchestrator, plus security and code reviews.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| New `scripts/browser.py`, standard library only and standalone (it imports no other bug-hunter script): `detect REPO` and `run --test F --base URL [--copy DIR]` | Splitting detection into `scope.py` and the runner into `finding_v1.py` | A draft fetches it at a pinned version, like `stub_server.py`, so the repro runs on another machine; one file holds the browser rules |
| `run` writes `bh.playwright.config.mjs` into the copy and runs `node node_modules/@playwright/test/cli.js test --config bh.playwright.config.mjs` with a JSON reporter. It then prints the same result shape as `replay`: `{"result": "pass"}`, `{"result": "fail", "step": 1, "message": …}` or `{"result": "not run: …"}` | `npx playwright test`; the `.bin` shim | No fetch, one command on every OS (the shim is a `.cmd` on Windows), and `classify` works unchanged |
| The wrapper config stands alone: chromium only, `workers: 1`, `retries: 0`, `baseURL` from `ACCEPT_BASE_URL`, `use.proxy.server` = that listener with bypass `<-loopback>`, and the one test file. It does not import the repo's own config | Importing the repo config (proposed in Q4) | A repo config can start a `webServer`, run a `globalSetup` or name browsers that aren't installed; none of these may run against a live target. A deviation from the Q4 wording |
| `live_proxy.py`: an absolute-form request whose origin is the listener's own URL is served as its path. One to any other origin keeps the existing 400, now also logged. CONNECT is refused by the existing `send_error` path (501, refusal header, log line) | 403 for another origin | The existing tests pin 400; the request is refused either way |
| `scope.py --live --browser` adds `browser: {available, reason, dir}`. When it is available, parts with UI files (by extension: `.tsx .jsx .vue .svelte .html .htm .ejs .hbs .erb .jinja .njk .astro`) are kept beside the route parts and get the `web-ui` edge input | Failing the run when Playwright is missing | Spec: "browser mode unavailable, reported"; the live hunt still runs |
| `isolate.py SCRATCH --browser` keeps `PLAYWRIGHT_BROWSERS_PATH` pointed at the real browsers folder (resolved before `HOME` moves) and sets `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`. No `playwright install` guard: the runner calls the CLI by path, so a shell function can't catch it, and the prompt rule stands alone | A wrapper that blocks `install` | Not cheap or reliable (orchestrator: "a guard if cheap") |
| Default-format browser drafts. Steps: the locked install, `curl -fsSLo browser.py https://raw.githubusercontent.com/tammai/bug-hunter/v<version>/scripts/browser.py`, a quoted heredoc writing `bh-repro.spec.ts`, then `python3 browser.py run --test bh-repro.spec.ts --base "$BASE"` with its output. The verifier copies `browser.py` from the plugin, as it does the stub | A browser-only format | Same pattern as the stub server; the draft runs from itself alone |
| finding-v1 browser repro: `## Repro (finding-v1)` holds one JSON object `{"runner": "playwright", "test": "<source>"}`; `## Observed (finding-v1)` holds `{"rebuild": <result>}`, plus `"reference"` under `--reference`. The finding's repro is `{"runner": "playwright", "test": …, "env": ["ACCEPT_BASE_URL", "ACCEPT_ACCOUNT_<NAME>"…]}` | A list of steps | C4's playwright runner takes one spec file |
| Fixture `tests/fixtures/browser-app/`: a Node `http` app whose form saves one record per submit, with no double-submit guard. `package.json` and `package-lock.json` pin `@playwright/test` 1.60.0, which matches the chromium build installed here (revision 1223). The lockfile is generated once with npm | Another version | The installed browser decides the version; any other version would need a download |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** spec §B3 (detection): Given a repo with `@playwright/test` in `devDependencies`, a tracked lockfile holding it, and a browsers folder with `chromium-1223`, when `browser.py detect REPO` runs, then it prints `available: true` and the package folder. With no devDependency, no lockfile entry, or no chromium build, it prints `available: false` and a reason naming the missing piece.
- **AC-002** spec §B3: Given `--live --browser`, when `scope.py` runs, then its output has `browser`; with Playwright available, a part made of UI files is kept with the `web-ui` edge input; with Playwright missing, only route parts are kept and `browser.reason` says why. Without `--browser`, the output is unchanged.
- **AC-003** spec §B3 / Q3: Given `--browser`, when `isolate.py SCRATCH --browser` runs, then its shell code sets `PLAYWRIGHT_BROWSERS_PATH` to the real browsers folder and `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`; without `--browser`, its output is unchanged.
- **AC-004** spec §B3 (the proxy is the only origin): Given a running proxy, when a client sends an absolute-form `GET http://<listener>/x`, then it is forwarded as `/x`; an absolute-form request to another origin (the other listener, another host) gets 400 and a log line; a CONNECT gets the refusal header and a log line.
- **AC-005** spec §B3 (wrapper config): Given a copy and a test file, when `browser.py run` writes its config, then the config sets `baseURL` and `use.proxy.server` from `ACCEPT_BASE_URL`, bypass `<-loopback>`, chromium only, `workers: 1`, `retries: 0` and only that test file, and holds no `webServer`.
- **AC-006** spec §B3 (run): Given a copy whose `node_modules/@playwright/test/cli.js` reports a passing or a failing test, when `browser.py run --test F --base URL` runs, then it prints `{"result": "pass"}` or `{"result": "fail", "step": 1, "message": <the first error line>}`; with no `node_modules` it prints `{"result": "not run: …"}`; it never runs `npx`.
- **AC-007** spec §B3 with §B4: Given a browser draft with a `{"runner": "playwright", "test": …}` repro and its Observed, when `finding_v1.py render` and `write` run (with `--rebuild`/`--reference` results under `--reference`), then the finding's repro is `{"runner": "playwright", "test": …, "env": […]}`, it passes `check_finding`, and `classify` gives the same classes as for an HTTP repro.
- **AC-008** spec §B3: `edge-inputs/web-ui.md` lists double submit, back/forward after a write, a stale tab, two tabs editing one record, long and RTL text, empty and huge lists, slow network, session expiry mid-form and keyboard-only flows. `[manual: content, checked in Review against the spec]`
- **AC-009** spec §B3: `/hunt --target <name> --browser` does these, and without `--browser` nothing changes. `[manual: prompt text, checked in Review]`
  - checks availability and reports it;
  - gives UI parts `web-ui`;
  - starts agents with `isolate.py --browser`;
  - has hunters and verifiers write and run one Playwright test through `browser.py run`, never `npx` or `playwright install`.
- **AC-010** spec §Acceptance: one browser-mode run on the fixture app finds the planted double-submit bug, and the verifier reproduces it. `[manual: live run, pre-approved at USD 8 by the orchestrator]`

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_browser.py › test_detect_needs_the_package_the_lockfile_and_a_browser | `uv run pytest tests/test_browser.py::test_detect_needs_the_package_the_lockfile_and_a_browser` |
| AC-002 | tests/test_browser.py › test_scope_keeps_ui_parts_when_the_browser_is_available | `uv run pytest tests/test_browser.py::test_scope_keeps_ui_parts_when_the_browser_is_available` |
| AC-003 | tests/test_browser.py › test_isolation_keeps_the_browsers_read_only | `uv run pytest tests/test_browser.py::test_isolation_keeps_the_browsers_read_only` |
| AC-004 | tests/test_browser.py › test_proxy_serves_absolute_form_only_for_itself | `uv run pytest tests/test_browser.py::test_proxy_serves_absolute_form_only_for_itself` |
| AC-005 | tests/test_browser.py › test_wrapper_config_pins_the_proxy_and_one_test | `uv run pytest tests/test_browser.py::test_wrapper_config_pins_the_proxy_and_one_test` |
| AC-006 | tests/test_browser.py › test_run_reports_pass_fail_and_not_run | `uv run pytest tests/test_browser.py::test_run_reports_pass_fail_and_not_run` |
| AC-007 | tests/test_browser.py › test_playwright_repro_becomes_a_finding | `uv run pytest tests/test_browser.py::test_playwright_repro_becomes_a_finding` |
| AC-008 | manual | content: Review checks `edge-inputs/web-ui.md` against spec §B3 |
| AC-009 | manual | prompt text: no test can run an agent; Review checks `commands/hunt.md`, `agents/bug-hunter.md` and `agents/repro-verifier.md` |
| AC-010 | manual | live run on the fixture app, orchestrator-approved budget USD 8; recorded in `knowledge/runs/` |

## Must never break

- Without `--browser`, `/hunt`, `scope.py`, `isolate.py` and `finding_v1.py` behave as on 5c0c8b9. The only proxy change is that an absolute-form request to its own listener is now served.
- Browser traffic goes through the proxy alone. Agents never see a target URL or a token. No browser or package is downloaded beyond the locked install.
- Nothing is written in the target repo; the wrapper config and the test file live in the throwaway copy.

## Failure modes

- Untrusted input: the test file is written by an agent and run only in the throwaway copy; the repo's `package.json` and lockfiles are parsed as text or JSON → AC-001, AC-006
- I/O errors (no `node`, no `node_modules`, a test that hangs or a report missing) → AC-006 (`not run`, with a timeout)

## Out of scope

- Departures (part 5); browsers other than chromium; a live `--browser --reference` run.

## Review

- **What fired:**
  - security, because `Risk: high`: a proxy change, a browser running agent-written test code, and the owner's browsers folder;
  - code, because `## Public Surface` isn't `- none`.
  - The orchestrator approved both. Security ran on `sdlc:code-reviewer` (opus) with the brief's security section; code ran on the built-in `code-review` (`high --max-findings all`). The user's review rule applied from round 2 (msg_0ab9cdbeb4d9): a 2-round cap, with only a HIGH security or privacy finding at round 2 fixed and checked.
- **Verdicts:** all four reports are in `.sdlc/.work/findings/2026-11-08-m-browser-mode/`.
  - security: `security-r1.md` FAIL (S-1), then `security-r2.md` PASS;
  - code: `code-reviewer-r1.md` FAIL (CR-1, CR-4), then `code-reviewer-r2.md` PASS.
- **High findings and their fixes.** Each fix started with a failing test, in `tests/test_browser.py`.
  - **S-1:** the `--reference` Classify step ran the hunter's test unisolated. `commands/hunt.md` now runs it under `isolate.py --browser`.
  - **CR-1 / N-1:** infra failures counted as bug evidence. `browser.py run` now reports "not run" for a proxy refusal during the test (`live_proxy.py`'s new `GET /.bug-hunter/refusals` count), for launch, network and timeout errors, and for a missing chromium revision.
  - **CR-4:** the fixture couldn't be scoped. It now routes through `app.get`/`app.post` and serves `public/index.html`, and templates near a part make it a UI part.
- **Medium and low bugs fixed in round 1:**
  - S-2: a closed `PLAYWRIGHT_DOWNLOAD_HOST`, plus the revision check;
  - S-3: `launchOptions.proxy`, and the proxy only behind bug-hunter's listener (N-2);
  - S-4: one `BH_TEST_END` per heredoc;
  - S-5 / CR-9: a dedicated `bh-run` test folder;
  - S-6: more refused-origin cases in the tests;
  - CR-2: the budget and rate sized for page loads;
  - CR-3: template UIs;
  - CR-5 / CR-6: the package folder, and a locked install required;
  - CR-8: longer messages;
  - CR-10: the outer timeout;
  - CR-12: tree kill;
  - CR-13 to CR-15 and CR-17: smaller fixes.
- **Tickets.** Round-2 findings were capped under the user's rule ("waived round 3: tickets"):
  - **Test timeouts:** a "Test timeout" counts as not run, so an element that never appears is missed (R2-1).
  - **Messages:** messages cut with no digest (R2-2).
  - **Rendered Steps:** finding-v1 rendered Steps lack the install, the fetch and `--copy` (R2-3).
  - **Heredoc rule:**
    - `\r` before `BH_TEST_END` (R2-4);
    - the heredoc rule only covers the exact quoted form (R2-11, M-3).
  - **Masking breaks pages:** host masking breaks `Set-Cookie` Domain and JS host strings (R2-5).
  - **Fail-open pin:** the proxy pin fails open when the refusals probe doesn't answer (R2-6, M-2).
  - **Root-part UI:** a root part counts any `.html` as UI (R2-7).
  - **Detect:** detect stops at the first candidate (R2-8).
  - **test.fail:** an unexpected pass of `test.fail()` reports not run (R2-9).
  - **Owner's folder:** the browsers folder is writable, and per-browser download hosts outrank the closed one (R2-10, L-3).
  - **Refusal counter:**
    - it is global across agents (R2-12);
    - third-party https subresources make a page always not run (N-3).
  - **Process tree:** the node test can outlive an agent's tool timeout in its own session (M-1).
  - **Stale test folder:** `bh-run` isn't emptied (L-1).
  - **Probe redirects:** `_refusals` follows redirects (L-2).
  - **Bare git:** `git` called bare on Windows, a pre-existing class (L-4).
  - **Cleanups:** R2-13 and R2-14, CR-16, CR-18, and test granularity (CR-19, CR-20, R2-15).
  - **Not applied:** `--oracle` with `--browser`.
- **Drift and manual checks:**
  - Deviations: the `--browser` flag and the standalone config (orchestrator-approved); `browser.py run --draft`; the edge-input list test; exports; the round-1 fixes; `drafts.py`; the fixture page.
  - Tests: `uv run pytest` gives 225 passed and 17 failed. All 17 are the Windows rows in `.sdlc/baseline.md` (diffed). AC-001 to AC-007 failed first, then passed.
  - AC-008 and AC-009 (manual): `edge-inputs/web-ui.md` and the `/hunt` and agent prompt text were checked against spec §B3 by both review rounds.
  - AC-010 (the live run): met. One browser-mode `/hunt` on the fixture app found the planted double submit, and the verifier reproduced it in a real browser; it cost $0.96 against the USD 8 cap. Record: [knowledge/runs/2026-11-08-p4-browser-notes-app.md](../../../knowledge/runs/2026-11-08-p4-browser-notes-app.md).
  - The run raised three tickets:
    - the fixture's comments hint at the defect;
    - the prompt's account example was copied into a draft that uses no account;
    - the `browser.py` fetch URL points at an unreleased tag.
- **Lessons filed:** [recurring-defects.md](../recurring-defects.md) gets one line: a test runner that reports infrastructure failures as test failures.
