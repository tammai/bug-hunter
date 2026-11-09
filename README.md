# bug-hunter

A Claude Code plugin that hunts reproducible edge-case bugs in a repo and writes an issue draft for each. A bug is kept only when its repro was run by a hunter and re-run by a separate verifier from the draft alone. It never posts anything: you pick what gets filed.

> **Status:** v0.3.3, released (see [Releases](https://github.com/tammai/bug-hunter/releases)). Live-validated on 2026-11-08: 18 `/hunt` and `/audit` runs on a Python CLI, a Node/TS service, a Go module, a running HTTP service and an audit target, recorded in [knowledge/runs/](knowledge/runs/). Start with `--max 1`.

## Install

You need Python 3.12 or newer and `git`. `/hunt-post` and the open-issues check also need `gh`, logged in.

In Claude Code:

```
/plugin marketplace add tammai/bug-hunter
/plugin install bug-hunter@bug-hunter
```

Or load it from a clone for one session:

```
git clone https://github.com/tammai/bug-hunter.git
cd /path/to/the/repo/you/want/hunted
claude --plugin-dir /path/to/bug-hunter
```

## Hunt

From the root of the repo you want hunted:

```
/hunt [paths…] [--max N]
```

1. **Scope.** It splits the repo's tracked source files into parts of up to 5 files from one folder, leaving out tests and non-code files. Paths limit it to those folders or files.
2. **Ask.** It shows the hunter count, the expected cost (about 100k tokens per hunter, plus about 20k per verifier) and the parts `--max` leaves out. Then it waits for your yes. Answer no and nothing runs.
3. **Hunt.** One `bug-hunter` agent per part reads the code and tries edge inputs: paths with spaces, CRLF, empty files, `B10` sorting before `B2`, missing JSON keys, failing subprocesses and more. It drops anything it can't reproduce and anything already known (open issues and earlier drafts).
4. **Verify.** A separate `repro-verifier` re-runs each draft's steps in a fresh copy, from the draft alone. Only drafts that reproduce are kept.
5. **Clean up and report.** It removes the run's working files and tells you how much space that freed. Then it lists the verified bugs, and what was dropped and why.
6. **Fix here, or save to post.** It asks what you want. **Fix here** writes nothing: the full drafts are in the session, so you can ask Claude to fix them right away. **Save all** or **save some** writes drafts for `/hunt-post`. Unsaved drafts are gone when the session ends, and only saved drafts count as "already known" in later hunts.

### Disk use

All the agents in one run share one folder, `<temp>/bug-hunter-XXXX`, made by `scripts/scratch.py`:

- **One clone per run.** It's shallow, with only the latest commit. Each agent copies it with copy-on-write (APFS clones on macOS, reflinks on btrfs and XFS, a plain copy anywhere else), so a copy costs almost nothing until the agent changes files.
- **One download cache per run.** npm, pnpm, Yarn, uv, pip, Poetry, Composer, Go and Bundler download each package once for all agents, and installs copy or clone out of it, never hardlink. Gradle, Maven, Cargo and Bun keep their own per agent. Gradle and Maven aren't safe to share between builds running at the same time, Cargo's folder also holds the config every build obeys, and Bun hardlinks its installs.
- **Cleanup.** Each agent deletes its copy and installed dependencies before it replies. The run folder is removed at the end, or when the command stops early, and you're told the size freed. Every `/hunt` and `/audit` first sweeps folders that earlier runs left more than 12 hours ago, and lists younger ones so you can remove them if no other run is going.

If `/hunt` isn't found, use `/bug-hunter:hunt` (and `/bug-hunter:hunt-post`).

### Hunt a running dev server or UAT

```
/hunt --target http://localhost:3000 [paths…] [--max N]
/hunt --target uat [paths…] [--max N]
```

Hunters read the code's routes and handlers, then send edge inputs to the running server: other users' IDs, missing or expired logins, bad fields, double submits, pagination bounds and more (`edge-inputs/live-http.md`). Only parts that define HTTP routes are hunted.

- **Allowed targets only.** A localhost URL with a port works as is. Anything else must be listed by name in `~/.bug-hunter/<host>/<owner>/<repo>/targets.json`, next to the drafts folder and outside the repo, and you name it, never type its URL. Never list production.

  ```json
  {"uat": {"url": "https://uat.example.com", "writes": false,
           "accounts": {"alice": {"Authorization": "Bearer …"},
                        "bob": {"Cookie": "session=…"}}}}
  ```

- **One proxy.** `/hunt` starts `scripts/live_proxy.py` on 127.0.0.1. It's the only way agents reach the target: it forwards to that one target, adds an account's headers, refuses `POST`, `PUT`, `PATCH` and `DELETE` unless `"writes": true` (localhost allows them), never follows redirects, masks the accounts' values and the target's address in what it returns, and stops at a request budget (200 per agent, 5 a second). Agents never see the target URL or the tokens; refresh expired tokens in the file yourself.
- **Drafts stay shareable.** Steps are `curl "$BASE/…" -H "$ALICE_AUTH"` with a `Set before running:` line, and `drafts.py check --repo <repo> --target <name>` fails a draft that names the host or holds a token.
- **Writes are listed.** The report lists every write the proxy forwarded, so you can clean up UAT.

Agents could still open a connection elsewhere: their instructions forbid it, as with the offline no-network rule.

### Drafts

Drafts you save are written outside the repo:

- `~/.bug-hunter/<host>/<owner>/<repo>/drafts/NN.md`;
- `~/.bug-hunter/local/<folder>/drafts/NN.md` for a repo without an `origin`.

Each draft has the same four sections:

- **What happens**
- **Steps to reproduce**, with the actual output
- **Expected**
- **Root cause**: file, function and lines

To check a draft by hand: `python3 scripts/drafts.py check <draft>`.

### What it finds, and what it doesn't

It finds real defects (wrong output, a crash, data loss, wrong state) that can be fixed in one or two files with a test. It doesn't report style, feature requests, design opinions, or problems that only show under load. It works best on code with clear inputs and outputs: CLIs, parsers, libraries, scripts, and the logic modules of backends and frontends.

| Stack | Files hunted | Edge-input list |
|---|---|---|
| Python | `.py` | `python-cli` |
| Node, TypeScript, Vue, Svelte | `.js` `.mjs` `.cjs` `.ts` `.tsx` `.jsx` `.vue` `.svelte` | `node` |
| Go | `.go` | `go` |
| Rust | `.rs` | `rust` |
| Java, Kotlin | `.java` `.kt` | `jvm` |
| Ruby | `.rb` | `ruby` |
| PHP | `.php` | `php` |
| C, C++, C#, Swift, Lua, Perl, shell | their usual extensions | generic only |

Every part also gets `generic`, and parts that call an HTTP API or a vendor SDK (axios, fetch, requests, `net/http`, the AWS SDK, Stripe, …) also get `integrations`: timeouts, 429 and 5xx, malformed or HTML bodies, non-idempotent retries, expired tokens, duplicate or out-of-order webhooks. Hunters reproduce these offline against `scripts/stub_server.py`, a local stand-in for the service that logs every request, never the real service. Each stack's test files (`*_test.go`, `*_spec.rb`, `UserTest.java`, `*.spec.ts`, `tests/`, …) are left out.

Dependencies are installed in the throwaway copy only from the repo's tracked lockfiles, with the locked command, and with install scripts off for npm, pnpm, Yarn 1, Bun and Composer: `npm ci --ignore-scripts`, `pnpm install --frozen-lockfile --ignore-scripts`, Yarn, Bun, `uv sync --frozen`, `poetry install --no-root`, `go mod download`, `cargo fetch --locked`, Bundler (frozen), `composer install --no-scripts --no-plugins`, Gradle and Maven (`./gradlew`, `./mvnw` or `mvn`). Lockfiles in test and fixture folders, and folders with shell-special characters in their names, get no install. Nothing else may reach the network. A locked install isn't sandboxed: Yarn 2+, uv, Poetry and Bundler can still build or run code the repo chooses, Cargo runs the toolchain a `rust-toolchain.toml` names (which can be a path in the repo), and Gradle and Maven fetch from URLs the repo sets. That's the same trust as running the repo's code. Agents run with their own home folder and caches under the scratch dir (`scripts/isolate.py`). Variables pointing into your home, JVM and Node option variables, any active virtualenv or conda env, and token, password and key variables are dropped; if isolation can't be set up, the agent's command doesn't run. Your runtime managers (rustup, pyenv, asdf, mise, nvm, SDKMAN), `JAVA_HOME`, the Android SDK and CA bundles keep working, but rustup, mise and the Android Gradle plugin can't install anything. Volta isn't kept: a Volta-pinned Node is fetched into the scratch dir. Proxy host and port flags in your JVM option variables are carried over, but proxy settings in `~/.gradle/gradle.properties` or `~/.m2/settings.xml` aren't, so behind a proxy set only there, Gradle and Maven installs fail. On Windows (Git Bash), `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `HOMEDRIVE`/`HOMEPATH`, `TEMP`, `TMP` and `TMPDIR` also move into the scratch dir, and `gh` gets a placeholder token so it can't fall back to a login stored in Credential Manager. Windows Credential Manager, the Windows OpenSSH agent and programs that find their folders without these variables (.NET and NuGet, PowerShell) are still reachable there. This keeps tools off your home; it isn't a sandbox. Code that needs a running service (a database, a browser, an external API) comes back as "couldn't reproduce" rather than a guess.

### Orchestrated runs (0.4, unreleased)

For a pipeline such as product-rebuild, which runs `/hunt` unattended and routes what it finds:

```
/hunt [paths…] --yes --budget 600000 --format finding-v1 --out <dir> --cost-log <file>
```

- **`--budget <tokens>`** starts hunters only while each one's worst case (100k plus 5 verifiers of 20k) fits, and reports the parts left out. The figures are fresh tokens; processed tokens with cache reads ran 3–18× higher in the live validation.
- **`--yes`** skips the cost question (only with `--budget`); the cost is still shown.
- **`--cost-log <file>`** appends one line per hunter and verifier in the contracts' `cost.jsonl` format (C7). The host reports one token total, so `tokens_in` and `tokens_out` are `null` and the total is in `tokens_total`.
- **`--format finding-v1 --out <dir>`** writes one `BH-NNNN.json` per verified bug in the contracts' finding format (C6) instead of drafts, to a folder outside the repo. Each has `class: build-defect`, `route: sdlc`, `verified_by: {agent: repro-verifier, result: reproduced}`, `observed.reference: "not run: no --reference"`, a `severity`, and the extra fields `title` and `draft` (the verified draft). Only drafts the verifier reproduced are written.

`repro` uses bug-hunter's own `cli` shape until the contracts settle one (contracts v1 defines only HTTP replay in detail):

```json
{"runner": "cli",
 "env": ["BASE", "BOB_AUTH"],
 "steps": [{"command": "python3 backlog.py next backlog.md", "stdout": "B10\n"}]}
```

Run the steps in order, each in a fresh shell started at the repo's root; `stdout` is what each printed, stdout and stderr together, as `2>&1` writes them. Each step stands alone: files an earlier step wrote are still there, but no `cd`, `export` or shell variable carries over (known limit: shell state shared between steps isn't supported yet). `env` (live hunts only) names the variables the steps read, from the draft's `Set before running:` line. In this mode the JSON is the source: the hunter writes the steps as a `## Repro (finding-v1)` section holding one fenced JSON list, `scripts/finding_v1.py render` writes the draft's visible Steps from it, the verifier re-runs the JSON steps (instead of the rendered Steps), and `finding_v1.py write` writes the finding from the list the verifier reproduced. In the rendered Steps each command starts with `$ `; a line inside a heredoc body or an output that happens to start with `$ ` is not a command. The JSON is what runs.

The contracts are vendored, byte-identical, in `contracts/v1/` (version 1.1.1); `python3 contracts/v1/contracts.py finding <file>` checks a finding.

### Hunt against a spec (0.4, unreleased)

```
/hunt --oracle <spec> [--max N] [--budget <tokens>] [--format finding-v1 --out <dir>]
```

For a rebuild with an rspec spec: `<spec>` is the folder holding `criteria.lock.json`. Parts are the spec's features, not folders: each gets its story, the `domain.md` sections the story cites, its `openapi.json` operations and its source files, found from the sdlc state files that list its criteria (`## Criteria`, `## Tasks`) or, failing that, the commits naming its change file (at most 8 files per feature). Features with a criterion below verification level 2 come first, then the most changed lines, then the most failure modes; the ranking is shown before the cost question. A bug's Expected must cite a criterion or a `domain.md` rule; a wrong behaviour nothing covers is kept as a spec-gap candidate (`Oracle: spec-gap`), which `--format finding-v1` writes as `class: spec-gap`, routed to rspec. `scripts/oracle.py scope` does the scoping and ranking.

### Hunt a web UI in a browser (0.4, unreleased)

```
/hunt --target <name> --browser [--max N]
```

Browser mode is available when three things hold, and `scope.py` says which one is missing when it isn't:
- a `package.json` lists `@playwright/test` in `devDependencies`;
- a tracked lockfile beside it holds that package;
- a chromium build is already installed in Playwright's browsers folder (`PLAYWRIGHT_BROWSERS_PATH`, or the platform default).

UI parts (components and templates) are then hunted beside the route parts, with the `web-ui` edge inputs.
- **The test:** each bug is proven as one Playwright test file, `bh-repro.spec.ts`. It reads the base URL from `ACCEPT_BASE_URL` and logins from `ACCEPT_ACCOUNT_<NAME>`, the contracts' names.
- **The run:** `scripts/browser.py run` writes its own Playwright config: chromium only, one worker, no retries, and the proxy as the browser's only origin, so a link or redirect to anywhere else fails. It runs the repo's locked Playwright with `node`, never `npx`.
- **Not used:**
  - the repo's own Playwright config, which could start a server against the target;
  - other browsers.
- **Downloads:** the browsers already installed on this machine are used read-only. A browser download fails: the download host points at a closed port. When the locked version needs a chromium build that isn't installed, the run says so instead of fetching it.
- **Not run, not a bug:** a test the proxy refused a request for (budget, writes, another origin), a browser that won't launch, a network error or a timeout reports "not run", never a failure.

Known limit: "never `playwright install`" is a rule in the agents' prompts; no guard enforces it.

### Hunt against a running reference (0.4, unreleased)

```
/hunt --target <rebuild> --reference <reference> --format finding-v1 --out <dir> [--oracle <spec>]
```

Both are names in `targets.json` (or localhost URLs), and they must be different servers. The proxy serves each on its own loopback listener: agents get `$BASE` (the rebuild) and `$REF_BASE` (the reference), never a URL or token, and each listener reaches only its own target. A named reference takes writes only when its entry has `"writes": true`; a localhost URL takes them, as for `--target`. Both share one request budget. A replay sends one account name to both targets, so give them the same account names; `--check` warns about any account that only one has.

The repro is a contracts C4 HTTP replay: the draft's `## Repro (finding-v1)` holds a JSON list of `{request, expect}` steps, where `expect` is what the spec says. The draft's `## Observed (finding-v1)` holds what `scripts/finding_v1.py replay` printed against each target: `{"result": "pass"}`, `{"result": "fail", "step": n, "message": …}`, or `{"result": "not run: …"}` when the proxy refused a request. Accounts come from `ACCEPT_ACCOUNT_<NAME>`, as in C4. After the verifier reproduces a draft, `/hunt` replays it against both targets itself, and `finding_v1.py classify` sets the class from those two results by script, not by an agent:

| Rebuild | Reference | Spec covers it | Class |
|---|---|---|---|
| wrong | correct, or wrong differently | — | `build-defect` |
| wrong | same wrong, and `Defect: yes` | yes | `build-defect`, with `propose_departure: reference-defect-not-copied` |
| wrong | same wrong, and `Defect: yes` | no | `reference-defect` |
| differs (not the same wrong as the reference) | — | matches an accepted entry of `departures.yaml` | `accepted-departure` (dropped, listed with its ID) |
| same as the reference | same | yes, and it says otherwise | `spec-gap` |
| wrong | not run | — | the class the spec gives alone |
| not run | — | — | `environment`, routed to the orchestrator for a retry |
| passes now, though the verifier reproduced it | — | — | `flaky`, routed to the orchestrator |

"Same wrong" means the same failing step with the same message. A generated value in the message, such as an ID, makes two equal defects look different, so they come out as `build-defect`, which a person always reviews. `Defect: yes` is a line under the draft's title saying the behaviour is wrong by the bug bar whatever the spec says (a crash, data loss, wrong stored state); the verifier must confirm it from the output. A rebuild that matches the reference when nothing says either is wrong is not a finding. Given `--target` and `--ref-target`, `write` refuses a finding whose results or draft show either target's host or a login. It decodes JSON, `\x`, HTML and percent escapes, and strips terminal colour codes, first. Known limit: a target with a plain host name (no dot, such as `http://uat`) is recognised only after a scheme (`https://uat`, `http://user@uat`) or with its port (`uat:4000`). A protocol-relative `//uat` with no scheme is not counted. Two targets must be two origins: the same scheme, host and port with different paths is refused.

With `--oracle <spec>`, `<spec>/departures.yaml` (contracts C5) is read; no file means no departures, and an invalid one stops the run. An entry matches a finding when it is decided (not `status: proposed`), one of its `match` items has `runner: http` and the pointer of the check the rebuild failed, and the rebuild's value there satisfies the item's rule. That check must be the repro's last, since nothing after it ran, and a draft with `Defect: yes` is never matched. An entry listing `criteria` matches only a finding citing one of them; else one listing `features` only a finding whose criterion is in one of them; an entry with neither matches any finding. A `departures.yaml` that is a link is refused. The value is read back from the replay's failure message, so a message cut for length never matches. The first matching entry in the file wins. Entries with no pointer, another runner or an empty `match` are for people only, and a browser repro is never matched. bug-hunter never writes the registry: it only proposes a departure (`propose_departure`) for a person to decide.

## File the ones you want

Read the drafts first: `/hunt-post` shows only titles before it files. Then, from the same repo:

```
/hunt-post 1 3 --label bug
```

It files only the drafts you name, from your own `gh` login, with the label you choose. It refuses before filing anything when:

- a draft is missing or fails the format check;
- two drafts share a number;
- `gh` isn't logged in.

Each filed draft is recorded in `posted.json` next to the drafts, so it's never filed twice. If filing stops part way, the drafts already filed stay recorded.

## Audit for security and personal data

Before a deploy, from the root of the repo:

```
/audit [paths…] [--max N]
```

It audits the code, config, schema and deployment files, security-relevant folders first, for:
- **Authorization:** IDOR, missing role checks, mass assignment.
- **Injection:** SQL, NoSQL, command, path traversal, SSRF, XSS.
- **Secrets:** in code, config or `.env` files.
- **Session and auth:** expiry, CSRF, rate limits, password hashing.
- **Personal data:** logged, returned beyond need, sent to third parties, stored unencrypted, or kept with no way to delete it.

It also runs `npm audit` or `composer audit` where the repo has those lockfiles. Like `/hunt`, it shows the cost and waits for your yes first.

Each finding has evidence at one of three levels:
- **proven:** a repro or a script showed it;
- **traced:** every step from input to problem is cited as `path:line` with the code;
- **advisory:** a dependency advisory.

Every finding an agent writes is checked by a second agent that gets only the finding and tries to disprove it. Only findings it can't disprove are kept; the rest are listed in the report as not confirmed.

**Output.** Findings go to `~/.bug-hunter/<host>/<owner>/<repo>/audit/NN.md`, readable only by you. Each has a Severity, Category, CWE, Proof, Where, Evidence, Impact and Fix. `REPORT.md` holds:
- the table, sorted by severity;
- a PII inventory: each personal field, and where it's logged, returned, sent, stored and deleted;
- what was dropped, and what wasn't covered.

Secret values never appear in any output. Every finding and report line is checked against the shapes of known key types (AWS, GitHub, Stripe, OpenAI, Anthropic, Slack, Google, JWTs, private keys, masked keys) and against fingerprints of every secret the scan found, so a known secret is caught anywhere in a line, and so are its 8-character slices (12 for all-lowercase or all-uppercase ones). Very short or word-like values (under 6 characters, numbers, `true`, a single short word) aren't fingerprinted, because ordinary text is full of them. A secret the scan didn't see and that has no known shape relies on the agents writing `<redacted>`, as they're told to; personal data relies on that rule too. Nothing is ever filed or posted: `/hunt-post` refuses audit findings.

**Tell it who may see what.** Write `~/.bug-hunter/<host>/<owner>/<repo>/policy.md` with:
- your roles and who may see whose data;
- the routes that are public by design;
- any extra fields that count as personal data for your business.

Without it, an authorization finding that rests on an assumed rule says so and is capped at medium.

**Not covered yet:** dependency audits for pnpm, Yarn, Python, Go, Rust, JVM and Ruby; security checklists beyond generic, Node and Vue; running services (findings that need a live database or API are traced, not proven); scanning deployed environments.

## Safety

Hunting runs the target repo's code on your machine. Run it only on repos you trust: container isolation isn't supported yet.

What it does to contain that:

- **Never changes the repo.** Agents have no edit tools and read the repo only. Code runs in a throwaway clone made by `scripts/throwaway.py`. The clone has the tracked files and their uncommitted changes, but no `origin` remote and no `.venv` or other untracked environments. It's refused when a symlink points outside it. Worktrees are handled.
- **Keeps your logins out of reach.** Every agent command runs without your `gh` token or config, your global git config and credential helpers, or your SSH agent. Agents never run `gh`.
- **Treats what it reads as data.** Repo files, issue titles (anyone can write them) and drafts are never taken as instructions.
- **Posts nothing on its own.** Only `/hunt-post` files, and only the drafts you name.

## Develop

```
uv sync --frozen
uv run pytest
uv run ruff check .
```

| Folder | What's in it |
|---|---|
| `commands/` | `/hunt`, `/hunt-post` and `/audit` |
| `agents/` | `bug-hunter`, `repro-verifier`, `security-auditor` and `finding-verifier` |
| `edge-inputs/` | the edge-input lists hunters work through |
| `security/` | the security and PII checklists auditors work through |
| `scripts/` | standard-library Python the commands call: `scope.py`, `known.py`, `drafts.py`, `post.py`, `throwaway.py`, `isolate.py`, `scratch.py`, `secrets_scan.py`, `findings.py`, `finding_v1.py`, `cost_log.py`, `oracle.py`, `browser.py` |
| `contracts/v1/` | the shared contracts, vendored byte-identical from tammai/product-rebuild; never edit them here |
| `tests/` | pytest for the scripts, and checks on the prompt files |

Changes go through sdlc (`/sdlc:start`). Principles: [constitution](docs/sdlc/constitution.md). Background: [BRIEF.md](BRIEF.md) and the [PRD](docs/sdlc/prd.md). Releases: [release runbook](knowledge/runbooks/release.md).

## License

[MIT](LICENSE)
