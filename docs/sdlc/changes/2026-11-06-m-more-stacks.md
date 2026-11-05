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
