# Hunt more stacks: Node/Vue, Go, Rust, JVM, Ruby, PHP

## Why

**Request (verbatim):** "can i hunt a nodejs backend and vue frontend?" → "yes, start that change" → "also widen the test target stacks" → "Both" (more stacks hunted, each covered by tests with a fixture repo).

v0.1.0 hunts a Node backend and Vue frontend only partly, and has three gaps:
- `.vue` files are never hunted.
- Only Python has its own edge-input list.
- Hunters may install dependencies, but the verifier refuses any step that reaches the network, so most drafts that need dependencies are dropped. This affects every stack, Python included.

This change makes the PRD's "edge-input list per kind of code" ([prd.md](../prd.md) Core capabilities 2, open question 2) real for Node (with Vue/Svelte), Go, Rust, Java/Kotlin, Ruby and PHP. It also lets both agents install dependencies the one safe way: from the repo's lockfile, with install scripts off where the tool allows. Our own suite gets a fixture repo per stack.

**The user's words:** "Both": hunt more stacks, each covered by tests with a fixture repo. The stacks are the ones offered: Go, Rust, Java/Kotlin, Ruby, PHP, plus Node/Vue and the existing Python.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| One data file, `scripts/stacks.json`, lists each stack's file extensions, edge-input list, test-file patterns and locked install commands; `scope.py` reads it and tags each part with `stacks` and `edge_inputs`, plus a top-level `installs` | Stack rules written in `hunt.md` and the agent prompts | Deterministic and testable per stack (constitution IV); one place to add a stack |
| Installs are allowed only as the exact commands `scope.py` lists in `installs`, run in that folder of the copy. They come from the lockfiles the repo tracks: `npm ci --ignore-scripts`, `pnpm install --frozen-lockfile --ignore-scripts`, `yarn install --frozen-lockfile --ignore-scripts` (Yarn 1) or `YARN_ENABLE_SCRIPTS=0 yarn install --immutable` (Yarn 2+, when `.yarnrc.yml` is tracked), `bun install --frozen-lockfile --ignore-scripts`, `uv sync --frozen`, `poetry install --no-root`, `go mod download`, `cargo fetch --locked`, `BUNDLE_FROZEN=true bundle install`, `composer install --no-scripts --no-plugins`, `./gradlew --no-daemon dependencies`, `mvn -B -q dependency:go-offline`. Every other network step stays refused | Letting agents pick their own install command; `npm install` | A lockfile pins what's fetched. Scripts off stops dependencies running code at install time. The verifier can check a step against a list instead of judging it |
| The verifier gets the repo's `installs` list with the draft (repo facts, not hunter reasoning) | Only the draft | It needs the list to tell an allowed install from a refused network step |
| Stacks: python (existing list kept), node (`.js .mjs .cjs .ts .tsx .jsx .vue .svelte`), go, rust, jvm (`.java .kt`), ruby, php. C, C++, C#, Swift, Lua, Perl and shell are still hunted with the generic list only | One list per language for everything | Matches the stacks asked for; the rest keep today's behaviour |
| Test-file patterns grow per stack: `_spec.rb`, `_test.rb`, `Test.java`/`Tests.java`, `Test.kt`, `Test.php`, `.test.`/`.spec.` (already there) | Hunting test files | Test files aren't targets; today `UserTest.java` would get a hunter |
| A part gets a stack when any of its files has that stack's extension; `generic` is always first | A part per stack | Parts stay folder-based, as today |
| A version bump and release aren't part of this change | Bumping here | The runbook releases separately; new edge-input lists make it v0.2.0 |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** prd.md §Core capabilities 1: Given a repo with `.vue` and `.svelte` files, when `scope.py` runs, then they're in its parts, tagged `node`.
- **AC-002** prd.md §Core capabilities 2: Given a fixture repo per stack (python, node, go, rust, jvm, ruby, php), when `scope.py` runs, then each part lists `stacks` and `edge_inputs` (`generic` first, then each stack's list, e.g. `["generic", "node"]`). A part with only C or shell files gets `["generic"]`.
- **AC-003** Given each stack's test-file patterns (`spec/a_spec.rb`, `UserTest.java`, `UserTest.kt`, `UserTest.php`, `src/__tests__/x.ts`, `x_test.go`), when `scope.py` runs, then none of them is in a part.
- **AC-004** Given tracked lockfiles at the root and in subfolders (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock` with or without `.yarnrc.yml`, `bun.lock`/`bun.lockb`, `uv.lock`, `poetry.lock`, `go.sum`, `Cargo.lock`, `Gemfile.lock`, `composer.lock`, `gradlew`, `pom.xml`), when `scope.py` runs, then `installs` lists `{"dir", "command"}` for each, with the exact command from the decision table, and it's `[]` when there are none.
- **AC-005** Every `edge_inputs` name in `stacks.json` has a non-empty `edge-inputs/<name>.md`. Every edge-input file is named by `stacks.json` or is `generic`. Each new list covers its stack's core traps:
  - node: `undefined`, `parseInt`, `==`, floating point, time zones, unhandled rejections, `JSON.parse`, default `sort()`;
  - go: nil maps, the loop variable, error shadowing, slice aliasing, `defer` in loops;
  - rust: `unwrap`, integer overflow, `as` casts, UTF-8 slicing, path joins;
  - jvm: `null`, `==` on strings, integer overflow, time zones, resource leaks;
  - ruby: `nil`, frozen strings, `Integer()` vs `to_i`, encodings, symbol vs string keys;
  - php: `==` juggling, `empty("0")`, `strpos` returning 0, array key casting, `json_decode` null.
- **AC-006** prd.md §Core capabilities 1: `commands/hunt.md` takes each part's edge-input lists from `scope.py`'s `edge_inputs`, not a rule of its own. It gives both agents the `installs` list.
- **AC-007** Constitution III: both agents allow dependency installs only as the exact commands in the `installs` list, run in the folder it names inside the copy. They name every other network step as refused. The verifier treats a draft step that matches an `installs` entry as allowed, and any other install as `CANNOT RUN`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_stacks.py › test_vue_and_svelte_files_are_hunted_as_node | `uv run pytest tests/test_stacks.py::test_vue_and_svelte_files_are_hunted_as_node` |
| AC-002 | tests/test_stacks.py › test_each_stack_gets_its_edge_inputs | `uv run pytest tests/test_stacks.py::test_each_stack_gets_its_edge_inputs` |
| AC-003 | tests/test_stacks.py › test_each_stacks_test_files_are_left_out | `uv run pytest tests/test_stacks.py::test_each_stacks_test_files_are_left_out` |
| AC-004 | tests/test_stacks.py › test_lockfiles_give_exact_locked_installs | `uv run pytest tests/test_stacks.py::test_lockfiles_give_exact_locked_installs` |
| AC-005 | tests/test_plugin_files.py › test_every_stack_has_an_edge_input_list_covering_its_traps | `uv run pytest tests/test_plugin_files.py::test_every_stack_has_an_edge_input_list_covering_its_traps` |
| AC-006 | tests/test_plugin_files.py › test_hunt_takes_edge_inputs_and_installs_from_scope | `uv run pytest tests/test_plugin_files.py::test_hunt_takes_edge_inputs_and_installs_from_scope` |
| AC-007 | tests/test_plugin_files.py › test_agents_allow_only_the_listed_locked_installs | `uv run pytest tests/test_plugin_files.py::test_agents_allow_only_the_listed_locked_installs` |

## Must never break

- Hunters and verifiers never write to the target repo, and code runs only in the `throwaway.py` copy (constitution III).
- No network step except the `installs` commands. The `gh` and git logins stay out of reach.
- Existing `scope.py` output (`parts` with `id`/`dir`/`files`, `skipped`, `hunters`, `est_tokens`) keeps its shape; the new fields only add to it.
- Scripts stay standard-library only.

## Failure modes

- **Untrusted input reaching a shell.** Lockfile paths come from the target. `installs` gives a folder and a fixed command from `stacks.json`, never text from the repo. A folder path with spaces or non-ASCII is quoted by the agent as a path → AC-004 (fixture folder with a space), AC-007.
- **Code running at install time.** Scripts are off where the tool allows (npm, pnpm, yarn, bun, composer). Gradle, Maven, Cargo and Go can still run build logic. That's the same trust the owner already gave by saying yes to running the repo's code → must-never-break line 2, AC-007.
- **A monorepo with several lockfiles** → AC-004 (root and subfolder).
- **A repo with no lockfile:** `installs` is `[]`, so an install step is `CANNOT RUN`, as today → AC-004.

## Out of scope

- Edge-input lists for C, C++, C#, Swift, Lua, Perl and shell.
- A live run on a Node/Vue repo: it follows the merge, as for v0.1.0.
- Running UIs in a browser, and services (database, Redis); those findings still come back as "couldn't reproduce".
- The version bump and v0.2.0 release (the runbook's job).
- Container isolation.

## Review

- **Recommended and chosen:** security + code (high), because `Risk: high` (the agents' network rule is loosened for installs, and folder paths from the target reach agent shell commands) and `## Public Surface` isn't empty; chosen by the user ("go ahead"). Rounds 3 to 7 were the user's choices: "fix", then "fix" under the rule that only new security findings block (logged), then "fix until no findings".
- **Verdicts:** in `.sdlc/.work/findings/2026-11-06-m-more-stacks/`.

  | Round | Security | Code (high) |
  |---|---|---|
  | r1 | FAIL S1–S3 | FAIL CR-1, CR-2 |
  | r2 | FAIL R2-1, R2-2 | FAIL CR2-1, CR2-2 |
  | r3 | FAIL R3-1, R3-2 | FAIL CR3-1, CR3-2 |
  | r4 | FAIL R4-1, R4-2 | PASS |
  | r5 | PASS | PASS |
  | r6 | PASS | PASS |
  | r7 | PASS | PASS |

  Both r7 reviewers say nothing left is worth another round. Dependency audit (`dependency-audit-r1.md`): not run. There are no runtime dependencies and `pip-audit` isn't installed.
- **Fixed** (each test-first, in `tests/test_stacks.py`, `tests/test_isolate.py` or `tests/test_plugin_files.py`):
  - **S1 / CR-2, injection through a folder name:** a folder with a quote, `$`, a backtick, a backslash, a control character or a leading `-` gets no install. Each install has an exact `step`, `(cd '<dir>' && cmd)`, which the verifier compares as text (CR-1, S4).
  - **S2 / R2-2 / R4-1, installs reading or writing the owner's home and credentials:** the new `scripts/isolate.py`, run fail-closed at the start of every agent Bash call, moves `HOME`, XDG, the tool caches and Java's `user.home` into scratch.
    - It drops inherited variables that point into the real home, the JVM and Node option variables, and secret-looking variables.
    - It keeps `PATH`, the runtime managers, `JAVA_HOME`, the Android SDK, CA bundles and proxy host/port flags.
  - **R2-1 / R3-1, Poetry installing into the owner's virtualenv or conda env, including via a committed `poetry.toml`:** active envs are unset, and `POETRY_VIRTUALENVS_CREATE` and `POETRY_VIRTUALENVS_IN_PROJECT` are forced.
  - **R3-2 / R4-2 / R2-3, repo files installing runtimes or SDKs into the real home:**
    - mise's four auto-install variables are 0.
    - Volta isn't kept.
    - `RUSTUP_AUTO_INSTALL=0`.
    - Android SDK downloads are off.
  - **CR2-1, Ruby gems not found by `bundle exec`:** `BUNDLE_PATH=vendor/bundle` is exported.
  - **CR2-2 / CR3-1 / CR3-2, runtimes lost when `HOME` moves:** asdf, mise (with `[tools]` only, from every config location and `conf.d`), nvm, SDKMAN, `JAVA_HOME` and `ANDROID_HOME` are kept.
  - **L-1 / T-1 / R6-1 / R6-2, writing through planted symlinks:** folders are opened with `O_NOFOLLOW` one level at a time and files are written atomically. A symlink at the top of the scratch home or in `.config` stops isolation.
  - **Fail-open isolation (CR4-1):** the agents' line is `ISO="$(…)" && eval "$ISO" || exit 1;`, and a test runs it.
  - **Also fixed:**
    - CR-3: no installs for test or fixture lockfiles.
    - CR-5: entries dedupe.
    - CR-7: non-ASCII folder test.
    - CR-8: `./mvnw` support and tool names.
    - S3 / CR-4 / R2-4: honest wording on what installs can still run.
    - `MAVEN_CONFIG`, mise system config, FIFOs, quoted proxy values, XDG mise config, and a second run in the same scratch (T7-1).
- **Tickets:**
  - CR-6: Gradle/Maven installs fetch metadata and miss some test-time plugins.
  - T7-3 / R7-1: a symlink planted at the scratch path itself is followed.
  - R7-2: links deeper in the scratch home, or planted after isolate.py exits, aren't caught.
  - N-2: whether mise reads `MISE_SYSTEM_DIR` is unverified (mise isn't installed here). The probe is in `security-r7.md`.
  - mise `conf.d` precedence is unverified against mise's source.
  - Volta users get no default Node.
  - Proxy settings in `gradle.properties` / `settings.xml` aren't carried (now in the README).
  - A live Node/Vue run.
- **Drift and manual checks:**
  - Every `## Deviations` line in the state file, rounds 1–7: the shared `isolate.py`, the changed Bundler command, two test asserts tightened to the new behaviour.
  - This file's Failure modes line "Gradle, Maven, Cargo and Go can still run build logic" was wrong: Cargo and Go fetch without running package code, unless a `rust-toolchain.toml` names a path. Yarn 2+, uv, Poetry and Bundler can run repo-chosen code. That's corrected in the README and `/hunt`.
  - No `manual` ACs.
- **Security:**
  - No high or critical findings open, and no secrets in the diff.
  - Isolation keeps tools off the owner's home; it isn't a sandbox. Code that runs with the owner's rights can still read files by absolute path. Container isolation stays out of scope.
- **Lessons filed:** [knowledge/gotchas/isolating-agents-without-a-sandbox.md](../../../knowledge/gotchas/isolating-agents-without-a-sandbox.md), [recurring-defects.md](../recurring-defects.md)
