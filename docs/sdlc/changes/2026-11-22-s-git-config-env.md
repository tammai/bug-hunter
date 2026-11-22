# Isolation drops git config passed through the environment

## Why

Request: "isolate.py: unset inherited GIT_CONFIG_PARAMETERS, GIT_CONFIG_COUNT and GIT_CONFIG_KEY_*/GIT_CONFIG_VALUE_* in the hunter's isolated environment, which can inject git config (e.g. a credential helper) without any file" (todo item from 2026-11-06-m-windows-isolation).

Proof: with `GIT_CONFIG_PARAMETERS="'credential.helper'='store'"`, `GIT_CONFIG_COUNT=2` and `GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` set in the owner's shell, `git config --list --show-origin` inside the isolated shell still lists `command line: credential.helper=store`, `credential.helper=cache` and `core.sshcommand=ssh -i key`.

Root cause: `_plan` hides git's global and system config files (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`), but git also reads config from these variables, and none of them matches `SECRET_NAME`, points into the home or is in `ALWAYS_UNSET`, so they pass through. An owner's credential helper or SSH command (and the credentials it unlocks) would reach the target's code and installs.

## Decisions

- Unset by pattern (`GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>`, `GIT_CONFIG_VALUE_<n>`), not a fixed list: the count is open-ended. Matched against the folded name, so Windows spellings in any case go too.
- Ruled out: exporting `GIT_CONFIG_COUNT=0`. That would leave `GIT_CONFIG_PARAMETERS` in place, and unsetting matches how every other inherited setting is dropped.

## Acceptance criteria

- AC-001: in the isolated shell, git sees no config from `GIT_CONFIG_PARAMETERS` or `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_<n>`/`GIT_CONFIG_VALUE_<n>` inherited from the owner's environment.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_isolate.py › test_git_config_from_the_environment_is_dropped | `uv run pytest tests/test_isolate.py -k test_git_config_from_the_environment_is_dropped` |

## Must never break

- Git still has no global or system config file in the isolated shell (`test_git_sees_no_global_or_system_config`).
- Other variables the owner set and isolation keeps (toolchains, CA bundles) still come through.

## Out of scope

- Git's other environment overrides (`GIT_CONFIG`, `GIT_CONFIG_SYSTEM`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`); the rest of the `isolate.py` follow-ups in `docs/sdlc/todo.md`.

## Review

- Fired: security (Risk: high). Code and UI did not fire (no public surface, no UI paths).
- Security round 1: PASS, no high findings. Report: `.sdlc/.work/findings/2026-11-22-s-git-config-env/security-r1.md`.
- Fixed in passing: a lost space in `JVM_OPTION_VARS = [` (F1); the KEY/VALUE index pattern is now ASCII `[0-9]+`, so a non-ASCII digit name never reaches `unset` (S2).
- Ticket: S1, every other inherited `GIT_*` override (`GIT_SSH`, `GIT_PROXY_COMMAND`, `GIT_DIR`, `GIT_EXEC_PATH`, …) still passes through; the structural fix is to unset all `GIT_*` but an allowlist. Filed in `docs/sdlc/todo.md`.
- Listed, not applied: S3, the test sets only uppercase names (Windows any-case folding is covered by an existing test).
- Full suite: only the 19 baselined Windows-only failures.
