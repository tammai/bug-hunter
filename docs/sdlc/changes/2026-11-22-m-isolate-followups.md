# Isolation keeps git's ssh off the owner's keys, strips proxy credentials, and refuses what it can't unset

## Why

**Request (verbatim):** "isolate.py follow-ups from the review of 2026-11-22-m-git-env-allowlist (docs/sdlc/todo.md item under ## Done, still open): (1) plain ssh finds owner's ~/.ssh via password database — isolation GIT_SSH_COMMAND with -F /dev/null and no identity (CR5); (2) _refuse_links checks by path on the descriptor path (R2-7); (3) env names that aren't shell identifiers surviving unset / proxy URLs with credentials; GIT_SSL_CAPATH/GIT_PROXY_SSL_CAINFO stay declined unless owner reopens. Feature name 2026-11-22-<track>-isolate-followups, risk high."

`scripts/isolate.py` is the safety boundary for every agent Bash call in `/hunt` and `/audit`. The review of [2026-11-22-m-git-env-allowlist](2026-11-22-m-git-env-allowlist.md) left four tickets in `docs/sdlc/todo.md`. Three of them are leaks of the owner's credentials into code the target controls (ssh keys, a registry token, a proxy password). The fourth is a gap in the planted-symlink check. All four are in the same file and its tests.

**The user's words:** At the gate (relayed by the coordinator), the owner approved the plan as written and answered: names bash can't unset, "Fail closed, as in AC-004"; `GIT_SSL_CAPATH` and `GIT_PROXY_SSL_CAINFO`, "keep dropped"; credentials in non-proxy URLs, "proxies only" (that proposal is dropped). They also deferred the review to the end of the build, where it runs across every parallel lane together.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Isolation exports its own `GIT_SSH_COMMAND`: `ssh -F /dev/null -o IdentityFile=none -o IdentitiesOnly=yes -o IdentityAgent=none -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes -o BatchMode=yes`. An owner's value is replaced, as the allowlist already does for `GIT_CONFIG_GLOBAL`. | `-F /dev/null` alone; pointing `HOME` somewhere else | ssh finds `~` through the password database, not `HOME`. `-F /dev/null` skips `~/.ssh/config`, but the default keys (`~/.ssh/id_*`) and `~/.ssh/known_hosts` still resolve there (`ssh -G` shows them). `IdentityFile=none` with `IdentitiesOnly` adds no key, and `IdentityAgent=none` closes the agent socket even when `SSH_AUTH_SOCK` comes back. |
| Known hosts: `/dev/null` with `StrictHostKeyChecking=yes`, so an unknown host fails. | A known-hosts file in the scratch home with `accept-new` | Git over ssh can't authenticate without the owner's keys anyway. Trusting a new host silently would only teach agents to work around a failure. The owner's `known_hosts` is never read or written. |
| This closes git's ssh only. A direct `ssh`/`scp` from target code still finds `~/.ssh`. The gotcha doc says so. | Wrapping `ssh` in a shell function | A function covers only this shell, not a child process that runs `ssh` by path. It is the same class as reading files by absolute path, which only a container stops. |
| `_refuse_links` on the descriptor path lists and checks the entries through the descriptor it opened (`os.scandir(fd)`, `DirEntry.is_symlink()`), not by path. | Adding `os.lstat` with `dir_fd` and growing the `_dir_fd()` set | `os.scandir` takes a descriptor wherever `os.scandir in os.supports_fd`, and it leaves `_dir_fd()` untouched. A wrong member of that set silently turns the descriptor path off (the `os.replace` gotcha). |
| **Fail closed** on an inherited variable that isolation must drop or change but bash can't, because its name isn't a shell identifier (`npm_config_//registry.npmjs.org/:_authToken`). Isolation prints one `error:` line naming the variable (never its value) and exits 1, so `eval "$ISO" || exit 1` stops the call. "Must drop or change" means a secret name, `GIT_*`, `ALWAYS_UNSET`, a path into the real home, or a proxy variable with credentials. **This needs the owner's OK** (gate question 2). | Warning and going on; refusing every non-identifier name | `unset` rejects such a name, and bash still passes it to every child process (checked: `env 'a-b=1' bash -c 'unset a-b; env'` prints `a-b=1`). No eval'd line can remove it. Refusing every such name would break Windows, where `ProgramFiles(x86)` is always set. The cost is that `/hunt` and `/audit` stop for an owner whose shell exports such a token, until they unset it. |
| Proxy credentials: any inherited variable whose name contains `PROXY` (any case; Windows folds) and whose value holds userinfo (`user[:pass]@` before the host) goes out with the userinfo removed, under the owner's spelling. Scheme, host, port and path stay. | Dropping proxy variables with credentials | This follows the JVM precedent (`PROXY_FLAG`): routing survives, users and passwords never do. A proxy that needs auth then answers 407 instead of the call going direct or hanging. |
| The userinfo is everything before the last `@` in the authority (up to the first `/`, `?` or `#` after an optional `scheme://`). That covers schemeless `user:pass@host:3128`, a user with no password, a raw `@` in a password, and IPv6 hosts (`[::1]:8080`). | `urllib.parse.urlsplit` | `urlsplit` reads a schemeless `user:pass@host` as scheme `user`, and it raises on a bad IPv6 bracket. A traceback here would print nothing and fail closed, but it would block the call for a value that only needs a cut. |
| `GIT_SSL_CAPATH` and `GIT_PROXY_SSL_CAINFO` stay dropped. | Keeping them | Declined at Define of 2026-11-22-m-git-env-allowlist. Revisit only if an owner hits it (gate question 3). |

**Bug:** four, each shown on macOS (bash 3.2, OpenSSH 10.5) at base 635113a.

1. **git's ssh uses the owner's ssh config, keys and known hosts (CR5).** `scratchpad/proof.sh` runs isolation in `env -i PATH=… HOME=<fake> https_proxy='http://me:hunter2@proxy.corp:8080' 'npm_config_//registry.npmjs.org/:_authToken=npm_SECRET'`, then prints what the agent's shell holds:
   ```
   npm_config_//registry.npmjs.org/:_authToken=npm_SECRET
   https_proxy=http://me:hunter2@proxy.corp:8080
   ssh command for git: unset
   identityfile ~/.ssh/<the owner's key, named in their ~/.ssh/config>
   userknownhostsfile /Users/<owner>/.ssh/known_hosts /Users/<owner>/.ssh/known_hosts2
   ```
   Root cause: ssh resolves `~` from the password database (`getpwuid`), so moving `HOME` changes nothing for it, and isolation sets no `GIT_SSH_COMMAND`. Even the owner's `~/.ssh/config` is read.
2. **A non-identifier secret name survives (line 1 of the output above).** Root cause: `_plan` filters the unset list with `re.fullmatch(r"[A-Za-z_]\w*", k)`, so it leaves such names out silently, and bash passes them on to children.
3. **A proxy password survives (line 2 above).** Root cause: nothing looks at proxy values. `SECRET_NAME` matches on names, and `https_proxy` isn't one.
4. **`_refuse_links` checks by path, not through its descriptor (R2-7).** `scratchpad/r27.py` plants a symlink in `scratch/home`, then wraps `_open_folder` so that after the folder is opened, the path is swapped for a clean folder. `_refuse_links(scratch, scratch/"home")` prints `refused: no (the link in the opened folder was missed)`. Root cause: `scripts/isolate.py:349` uses `os.path.islink(folder / name)`, which re-walks the path, so it checks a different folder from the one `os.listdir(fd)` listed.

**Proposals not asked for:** strip credentials from every inherited URL value, not just proxy ones (`PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `npm_config_registry`, `DATABASE_URL`). It is the same class, but the request names proxies. Dropped unless you keep it.

## Acceptance criteria

- **AC-001** Given the owner's shell sets its own `GIT_SSH_COMMAND`, when an isolated shell runs `git ls-remote` on an `ssh://` URL, then git starts `ssh` with `-F /dev/null`, `IdentityFile=none`, `IdentitiesOnly=yes`, `IdentityAgent=none`, `UserKnownHostsFile=/dev/null`, `StrictHostKeyChecking=yes` and `BatchMode=yes`, and the owner's command is not run.
- **AC-002** In an isolated shell, the ssh that `GIT_SSH_COMMAND` names resolves no identity file and no known-hosts file in the password database's home (`ssh -G`). Skipped where `ssh` is missing.
- **AC-003** On the descriptor path, `_refuse_links` refuses a symlink in the folder it opened, even when the path was swapped for a clean folder after the open.
- **AC-004** Given an inherited variable that isolation must drop but whose name isn't a shell identifier (a token `npm_config_//registry.npmjs.org/:_authToken`, a path into the real home, or a proxy URL with credentials), isolation exits 1, prints one `error:` line naming the variable and not its value, writes nothing to stdout, and shows no traceback.
- **AC-005** An inherited variable whose name isn't a shell identifier but which isolation keeps unchanged (`a-b=1`) still lets isolation succeed, and it reaches child processes unchanged.
- **AC-006** Given proxy variables with credentials in any case (`https_proxy`, `HTTP_PROXY`, `ALL_PROXY`, `npm_config_https_proxy`), a child process in the isolated shell sees each with the userinfo removed and the rest kept. This covers `http://me:hunter2@proxy.corp:8080/` → `http://proxy.corp:8080/`, a schemeless `me:pw@proxy:3128` → `proxy:3128`, a user with no password, a password holding `@`, and `http://u:p@[::1]:8080` → `http://[::1]:8080`. `NO_PROXY` and a proxy without credentials are unchanged.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_isolate.py › test_git_over_ssh_runs_isolations_ssh_not_the_owners | `uv run pytest tests/test_isolate.py -k test_git_over_ssh_runs_isolations_ssh_not_the_owners` |
| AC-002 | tests/test_isolate.py › test_isolations_ssh_finds_nothing_in_the_owners_ssh_folder | `uv run pytest tests/test_isolate.py -k test_isolations_ssh_finds_nothing_in_the_owners_ssh_folder` |
| AC-003 | tests/test_isolate.py › test_refuse_links_checks_the_folder_it_opened_not_the_path | `uv run pytest tests/test_isolate.py -k test_refuse_links_checks_the_folder_it_opened_not_the_path` |
| AC-004 | tests/test_isolate.py › test_a_variable_bash_cant_unset_stops_isolation | `uv run pytest tests/test_isolate.py -k test_a_variable_bash_cant_unset_stops_isolation` |
| AC-005 | tests/test_isolate.py › test_a_variable_bash_cant_unset_stops_isolation | `uv run pytest tests/test_isolate.py -k test_a_variable_bash_cant_unset_stops_isolation` |
| AC-006 | tests/test_isolate.py › test_proxy_credentials_are_dropped_and_routing_kept | `uv run pytest tests/test_isolate.py -k test_proxy_credentials_are_dropped_and_routing_kept` |

AC-004, AC-005 and AC-006 check the environment through a child process (`python3 -c` printing `os.environ`), not bash's `compgen -e`, which can't see names that aren't identifiers. AC-003 skips on Windows, which has no descriptor path. `test_every_inherited_git_override_is_dropped` is updated to allow isolation's own `GIT_SSH_COMMAND` and pin its value over the owner's.

## Must never break

- Every other inherited `GIT_*` is still dropped, and `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, `GIT_TERMINAL_PROMPT`, `GIT_EDITOR` and `GIT_PAGER` hold isolation's values (`test_every_inherited_git_override_is_dropped`, `test_git_sees_no_global_or_system_config`).
- Planted symlinks and junctions are still refused on both paths (`test_planted_links_anywhere_at_the_top_of_the_scratch_home_stop_isolation`, `test_the_path_fallback_refuses_planted_links`). The descriptor path stays on for this POSIX Python (`test_the_descriptor_path_is_on_for_this_posix_python`).
- JVM proxy routing still survives and JVM proxy passwords don't (`test_proxy_flags_survive_but_proxy_passwords_do_not`).
- On POSIX, undecodable environment bytes still pass through unchanged (`test_undecodable_environment_bytes_dont_break_isolation`).
- Windows' always-present `ProgramFiles(x86)` and similar names never stop isolation (AC-005 covers the shape).
- Isolation fails closed: any error prints nothing on stdout.

## Failure modes

- Untrusted input: the environment, with any name shape, case or encoding. Covered by AC-004, AC-005 and AC-006.
- A proxy value matching misses (schemeless, IPv6, `@` in the password). Covered by AC-006.
- Another platform's ssh: Git for Windows' ssh is MSYS's, which takes `/dev/null`. This can't be checked here, so it joins the Windows-only checks for the planned Windows session.
- Other readers: the gotcha doc `knowledge/gotchas/isolating-agents-without-a-sandbox.md` says plain ssh still finds `~/.ssh`. It is reworded in this change. The agent prompts' isolation bullets stay true and aren't edited.
- Concurrency, persisted data, deploy and rollback: none apply (a stateless script that prints shell code).

## Out of scope

- `GIT_SSL_CAPATH` and `GIT_PROXY_SSL_CAINFO` (declined, as above).
- Credentials in non-proxy URL variables, unless you keep the proposal above.
- A direct `ssh`/`scp` from target code reading `~/.ssh` by absolute path. Only a container stops that.
- Ticking the item in `docs/sdlc/todo.md`, which is left to the owner for this parallel run.

## Review

- **Recommended and chosen:** security and code, because `Risk: high` triggers both. The owner deferred every lane's reviews to the end of all builds. The coordinator ran them, and the owner approved each round past the cap.
- **Verdicts** (reports in `.sdlc/.work/findings/2026-11-22-m-isolate-followups/`):
  - **Round 1:** security `security-r1.md` FAIL (S1); code `code-reviewer-r1.md` FAIL (CR1-1).
  - **Round 2:** security `security-r2.md` FAIL (R2-1, R2-2); code `code-reviewer-r2.md` PASS (it listed the same two plus lows).
  - **Round 3:** security `security-r3.md` FAIL (R3-1).
  - **Round 4:** security `security-r4.md` PASS, with no high or medium findings. Its lows were fixed without another round.
  - Hooks blocked some reviewers' own writes, so the builder saved the round-2, round-3 and round-4 reports from the coordinator's relay as short lists of the findings.
- **Fixed** (each with a test that failed first; all in `tests/test_isolate.py`):
  - **CR1-1 (high):** a name with a newline or ESC could split the error line or write terminal escapes. One helper, `_shown` (unicode_escape), now escapes names in both the fail-closed error and `_unwritable` (`test_error_lines_escape_control_characters_in_names`).
  - **S1, CR1-2, R2-1, R3-2:** an exported bash function is removed with `unset -f`, but only when its value starts with `() {` and its name couldn't carry a credential. Every other `BASH_FUNC_` name goes through the credential gate (`test_exported_bash_functions_are_removed_not_refused`, `test_only_real_functions_that_hold_no_credential_skip_the_checks`).
  - **CR1-3, S2 (owner decision):** isolation fails closed only for odd names that could carry a credential. Odd names holding only a path pass through, including `ProgramFiles(x86)`, a JetBrains variable in the profile and `!C:` (`test_a_variable_bash_cant_unset_stops_isolation`).
  - **CR1-4, R2-2, R3-1 (high), L4:** splitting proxy lists left part of a password behind, for a separator inside the password or digits that read as a port. By the owner's decision, every PROXY value is now cut once between the scheme and the last `@`. The surviving host takes the scheme of its own entry (a known scheme only) or none (`test_proxy_values_never_keep_part_of_a_password`, `test_a_credentialed_list_keeps_the_scheme_of_the_surviving_entry`).
  - **R2-4:** the proxy credential check runs even when a name is dropped for another reason.
  - **CR1-5:** the error names every stuck variable.
  - **CR1-6:** new tests for a non-ASCII secret name and an odd `GIT_` name.
  - **R2-5:** the AC-002 ssh test no longer skips on Windows.
  - **R3-3, L3:** the function tests assert in a child process.
  - **CR1-8, R3-5, F1, L1:** docs updated: README, the gotcha doc, `copying-a-target-repo.md`, and the docstring.
- **Tickets:**
  - S3/CR1-7: secrets in names `SECRET_NAME` misses (`PROXY_PASS`, `PROXY_PWD`, `SSHPASS`, `MYSQL_PWD`).
  - R2-3: odd names for key or cert files (the owner's call).
  - R3-4: an odd PROXY name holding a harmless `@` now stops isolation (it fails closed).
  - `BASH_FUNC_token+x%%` is refused rather than removed (the safe side).
  - L2: bash 5 keeps a failed `%%` import as a variable; only a home path can survive that way.
  - The Windows session: Git for Windows' ssh with `-F /dev/null`, real `=C:` and JetBrains variables, and the AC-001 fake-ssh and function-body tests under Git Bash.
- **Drift and manual checks** (every Deviations line in the state file):
  - AC-005 shares AC-004's test.
  - Proxy credentials are cut at the last `@`, not in the authority alone.
  - The owner's CR1-3 decision supersedes AC-004's "a path into the real home"; AC-004 now reads "a variable that could carry a credential".
  - The owner's R3-1 decision supersedes the CR1-4 and R2-2 list-splitting fixes.
  - The owner's R3-2 gate means an exported secret-named function (`get_token`, and `git_author`, which matches `AUTH`) stops isolation again, reversing round 1's S1 expectation.
  - README and `copying-a-target-repo.md` were edited beyond the planned files.
  - Each round's `isolate.py` fixes, and four test changes. Each test change was re-shown failing at base, before Base moved.
  - Rebased onto `fdd1072`, with Base moved to that merge-base.
  - The coordinator asked for the todo item to be ticked at ship; its tickets stay open as a new item.
  - There are no manual ACs.
- **Security:** no high or critical finding is open, and there are no secrets in the diff. No dependency audit ran: the project has no runtime dependencies, the change adds none, and `pip-audit` isn't installed (not counted as a pass).
- **Lessons filed:** [knowledge/gotchas/isolating-agents-without-a-sandbox.md](../../../knowledge/gotchas/isolating-agents-without-a-sandbox.md) (ssh, names bash can't unset, proxy credentials, the descriptor check) and two lines in [recurring-defects.md](../recurring-defects.md).
