# bug-hunter

A Claude Code plugin that hunts reproducible edge-case bugs in a repo and writes an issue draft for each. A bug is kept only when its repro was run by a hunter and re-run by a separate verifier from the draft alone. It never posts anything: you pick what gets filed.

> **Status:** v0.1.0, not yet released. The scripts are tested, but there hasn't been a live `/hunt` run yet, so start with `--max 1`.

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
5. **Draft.** The report lists the kept drafts, and what was dropped and why.

If `/hunt` isn't found, use `/bug-hunter:hunt` (and `/bug-hunter:hunt-post`).

### Drafts

Drafts are written outside the repo:

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

Dependencies are installed in the throwaway copy only from the repo's tracked lockfiles, with the locked command, and with install scripts off for npm, pnpm, Yarn 1, Bun and Composer: `npm ci --ignore-scripts`, `pnpm install --frozen-lockfile --ignore-scripts`, Yarn, Bun, `uv sync --frozen`, `poetry install --no-root`, `go mod download`, `cargo fetch --locked`, Bundler (frozen), `composer install --no-scripts --no-plugins`, Gradle and Maven (`./gradlew`, `./mvnw` or `mvn`). Lockfiles in test and fixture folders, and folders with shell-special characters in their names, get no install. Nothing else may reach the network. A locked install isn't sandboxed: Yarn 2+, uv, Poetry and Bundler can still build or run code the repo chooses, Cargo runs the toolchain a `rust-toolchain.toml` names (which can be a path in the repo), and Gradle and Maven fetch from URLs the repo sets. That's the same trust as running the repo's code. Agents run with their own home folder and caches under the scratch dir (`scripts/isolate.py`). Variables pointing into your home, JVM and Node option variables, any active virtualenv or conda env, and token, password and key variables are dropped; if isolation can't be set up, the agent's command doesn't run. Your runtime managers (rustup, pyenv, asdf, mise, nvm, SDKMAN), `JAVA_HOME`, the Android SDK and CA bundles keep working, but rustup, mise and the Android Gradle plugin can't install anything. Volta isn't kept: a Volta-pinned Node is fetched into the scratch dir. Proxy host and port flags in your JVM option variables are carried over, but proxy settings in `~/.gradle/gradle.properties` or `~/.m2/settings.xml` aren't, so behind a proxy set only there, Gradle and Maven installs fail. This keeps tools off your home; it isn't a sandbox. Code that needs a running service (a database, a browser, an external API) comes back as "couldn't reproduce" rather than a guess.

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
| `scripts/` | standard-library Python the commands call: `scope.py`, `known.py`, `drafts.py`, `post.py`, `throwaway.py`, `isolate.py`, `secrets_scan.py`, `findings.py` |
| `tests/` | pytest for the scripts, and checks on the prompt files |

Changes go through sdlc (`/sdlc:start`). Principles: [constitution](docs/sdlc/constitution.md). Background: [BRIEF.md](BRIEF.md) and the [PRD](docs/sdlc/prd.md). Releases: [release runbook](knowledge/runbooks/release.md).

## License

[MIT](LICENSE)
