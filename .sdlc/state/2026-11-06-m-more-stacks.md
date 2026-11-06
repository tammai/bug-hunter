# 2026-11-06-m-more-stacks
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-06-m-more-stacks.md   (this feature's record for people)
Track: M   (sized up because: footprint ~16 files across scripts, prompts and edge-input lists; footprint: 16 files)
Risk: high   (loosens the agents' network rule for dependency installs; target-derived paths reach agent shell commands)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-06
Base: 682ac61
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: b57bceb tree 3761eac178f1513736b268ce60d28f175e0aff34
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- scope.py _build groups by folder (scripts/scope.py:71); stacks tag parts, not split them
- hunt.md step 1.4 hard-codes the .py rule today (commands/hunt.md); replace with scope's edge_inputs
- Verifier currently refuses all network (agents/repro-verifier.md:15); hunter says npm ci allowed (agents/bug-hunter.md:13): the contradiction this fixes

## Tasks
1. **stacks.json and scope.py tagging, test patterns, installs** — AC-001 AC-002 AC-003 AC-004
   - Files: `scripts/stacks.json`, `scripts/scope.py`, `tests/test_stacks.py`
2. **Edge-input lists node, go, rust, jvm, ruby, php** — AC-005
   - Files: `edge-inputs/node.md`, `edge-inputs/go.md`, `edge-inputs/rust.md`, `edge-inputs/jvm.md`, `edge-inputs/ruby.md`, `edge-inputs/php.md`, `tests/test_plugin_files.py`
3. **/hunt and agents: edge_inputs and installs** — AC-006 AC-007
   - Files: `commands/hunt.md`, `agents/bug-hunter.md`, `agents/repro-verifier.md`, `tests/test_plugin_files.py`
4. **Docs** — AC-001
   - Files: `README.md`

## Public Surface
- scope.py JSON: parts[].stacks, parts[].edge_inputs, installs — AC-002 AC-004
- scripts/stacks.json — AC-002 AC-004

## Gate log
- 2026-11-06 Stage 1: pass — change file approved by the user
- 2026-11-06 Stage 2: pass
- 2026-11-06 review: ran security, code high (Risk: high; Public Surface); chosen by the user (go ahead with the recommendation)
- 2026-11-06 Stage 3: fail — review r1: security S1-S3 (S4 too), code CR-1, CR-2 (+CR-3, 5, 7, 8 fixed now; CR-6 ticket)
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r2: security R2-1, R2-2; code CR2-1, CR2-2; user chose one more fix round (also R2-3, R2-4, R2-5 wording, keyring)
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r3: security R3-1, R3-2; code CR3-1, CR3-2; user chose round 4 (also R3-3, CR3-3, CR3-4)
- 2026-11-06 user rule for round 4 and after: a new security finding (writes outside scratch, reads owner credentials) is fixed before ship; a new functional gap that only makes a hunt return couldn't-reproduce is a ticket
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r4: security R4-1, R4-2 (+L-1..L-4); code passed with CR4-1..CR4-5 tickets; user: fix until no findings
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: pass — review r5 passed both; round 6 fixes the remaining tickets (user: fix until no findings)
- 2026-11-06 Stage 2: pass

## Deviations
- 2026-11-06 scripts/isolate.py, tests/test_isolate.py, agents/*.md What: new script the agents eval at the start of every Bash call: HOME, XDG and tool caches (npm, Cargo, Go, Gradle, Java user.home, Composer) move into scratch; token/password/key variables and SSH_AUTH_SOCK are unset; gh/git isolation moves here from the prompt text. Why: review S2, installs read ~/.m2/settings.xml, ~/.npmrc and ~/.netrc and wrote outside the copy. Effect: the two earlier prompt-text asserts on GH_CONFIG_DIR / GIT_CONFIG_GLOBAL now assert the eval line; tests/test_isolate.py checks the variables themselves.
- 2026-11-06 scripts/scope.py, scripts/stacks.json What: installs gain an exact step ((cd '<dir>' && cmd), bare at root); folders with quote, $, backtick, backslash, control characters or a leading - get no install, with a warning; lockfiles under test/fixture folders are skipped; entries dedupe; ./mvnw supported and preferred over mvn; Bundler gets BUNDLE_PATH=vendor/bundle. Why: review S1/CR-2 (injection through folder names), CR-1/S4 (install step not checkable), CR-3, CR-5, CR-8, S2 (Bundler writing to system gems). Effect: AC-004's Bundler command changed; new output field installs[].step.
- 2026-11-06 docs/sdlc/changes/2026-11-06-m-more-stacks.md (Failure modes) What: the residual-risk line was wrong; Cargo and Go fetch without running package code, while Yarn 2+, uv, Poetry and Bundler can build or run repo-chosen code and Gradle/Maven fetch from repo-set URLs. Why: review S3/CR-4. Effect: corrected in README and /hunt's cost message; the change file's Define text is left as written and corrected in its Review.
- 2026-11-06 scripts/isolate.py, scripts/stacks.json, agents/*.md, README.md, commands/hunt.md What: round 3 at the user's request. isolate.py drops inherited variables pointing into the real home (except PATH and runtime managers), VIRTUAL_ENV/CONDA_PREFIX/CONDA_DEFAULT_ENV/PYTHONHOME; keeps rustup, pyenv, asdf, mise, Volta, nvm, SDKMAN, GOROOT; exports POETRY_VIRTUALENVS_IN_PROJECT, BUNDLE_PATH=vendor/bundle (prefix dropped from the Bundler command), RUSTUP_AUTO_INSTALL=0, a null keyring backend; agents run it as python3 -I. Wording: Cargo via rust-toolchain.toml named, scripts-off tools named, isolation not called a sandbox. Why: review r2 security R2-1, R2-2 (+R2-3, R2-4, R2-5, keyring note), code CR2-1, CR2-2. Effect: AC-004's Bundler command is back to BUNDLE_FROZEN=true bundle install.
- 2026-11-06 scripts/isolate.py, tests/test_isolate.py What: round 4. Export POETRY_VIRTUALENVS_CREATE=true and four MISE_*_AUTO_INSTALL=0; VOLTA_HOME no longer kept (its shims would fetch into the real home); MISE_CONFIG_DIR moves to scratch with a copy of the owner's [tools] only; the owner's ~/.tool-versions is copied; JAVA_HOME, ANDROID_HOME/SDK_ROOT and CA-bundle variables kept when set; _JAVA_OPTIONS and JDK_JAVA_OPTIONS unset; a HOME of / or // drops nothing. Why: review r3 security R3-1, R3-2, R3-3; code CR3-1, CR3-2, CR3-3, CR3-4. Effect: two round-3 asserts on VOLTA_HOME and MISE_CONFIG_DIR changed to the new behaviour; Volta users' Node comes from scratch (a functional gap, a ticket).
- 2026-11-06 scripts/isolate.py, agents/*.md, README.md What: round 5. Unset JAVA_OPTS, MAVEN_OPTS, MAVEN_ARGS, GRADLE_OPTS, NODE_OPTIONS, MISE_GLOBAL_CONFIG_FILE, MISE_SYSTEM_CONFIG_FILE; android.builder.sdkDownload=false in the scratch gradle.properties; agents' isolation line fails closed (ISO=$(...) && eval || exit 1); scratch-home files replace planted symlinks instead of writing through; mise tools read from custom locations and table form, never crashing on odd configs; more CA variables kept. Why: review r4 security R4-1, R4-2, L-1..L-4; code CR4-1, CR4-2, CR4-4, CR4-5; user: fix until no findings. Effect: the agents' isolation line changed (test pins it); CR4-3 (Volta default Node) stays documented.
- 2026-11-06 scripts/isolate.py, tests/test_isolate.py What: round 6 (remaining tickets). Refuse and stop when any folder under the scratch home is a symlink; atomic temp-file + os.replace writes; read only regular version files; MAVEN_CONFIG unset; MISE_SYSTEM_CONFIG_FILE points at a never-created scratch path; XDG_CONFIG_HOME mise config read; proxy host/port/nonProxyHosts flags carried from dropped JVM option variables into JAVA_TOOL_OPTIONS (never users or passwords). Why: review r5 tickets T-1..T-5 (security), T5-1..T5-4 (code); user: fix until no findings. Effect: the round-5 assert that MISE_SYSTEM_CONFIG_FILE is absent now checks it isn't the owner's file.

## Open questions
-
