---
type: gotcha
title: Isolating agents with environment variables leaks in many ways
description: Why scripts/isolate.py is shaped as it is, and the traps that cost seven review rounds.
---

# Isolating agents without a sandbox

Agents run every Bash call behind `scripts/isolate.py` (fail closed: `ISO="$(python3 -I …)" && eval "$ISO" || exit 1;`). Moving `HOME` alone isn't enough; each trap below was a real review finding on 2026-11-06:

- **Absolute paths already expanded:** shell profiles export `PNPM_HOME`, `UV_CACHE_DIR`, `NPM_CONFIG_USERCONFIG` and friends with the real home in them. Drop every inherited variable that points into the real home, then keep an explicit list (PATH, runtime managers, `JAVA_HOME`, Android SDK, CA bundles).
- **Java ignores `HOME`:** `user.home` comes from the password database, so Maven reads `~/.m2/settings.xml` (and its server credentials) unless `JAVA_TOOL_OPTIONS=-Duser.home=…`. `_JAVA_OPTIONS`, `JAVA_OPTS`, `MAVEN_OPTS`, `MAVEN_ARGS`, `MAVEN_CONFIG` and `GRADLE_OPTS` can override it, so drop them and carry only proxy host/port flags.
- **Active environments:** `VIRTUAL_ENV` or `CONDA_PREFIX` makes Poetry install into the owner's env; a committed `poetry.toml` can turn venv creation off. Force `POETRY_VIRTUALENVS_CREATE` and `…_IN_PROJECT`.
- **Runtime managers cut both ways:** hide them and `node`/`ruby`/`java` stop resolving; keep them pointed at the real home and a repo's version file auto-installs there (mise, Volta, rustup, the Android Gradle plugin). Keep the locators, turn auto-install off, and copy only the owner's global version lists (`.tool-versions`, mise `[tools]`, never `[env]`).
- **Fail-open `eval "$(cmd)"`:** an empty or failed substitution still runs the rest of the call unisolated. Assign first and `|| exit 1`.
- **Planted symlinks:** code from an earlier call can link a scratch folder to the real home. Open folders one level at a time with `O_NOFOLLOW`, write via temp file + rename relative to the folder's descriptor, and refuse links at the top of the scratch home.
- **Run the script with `python3 -I`:** an owner's `PYTHONHOME` or `PYTHONPATH` would break or hijack it.

What it still can't stop: code running with the owner's rights reading files by absolute path. Only a container fixes that.

From [2026-11-06-m-more-stacks](../../docs/sdlc/changes/2026-11-06-m-more-stacks.md).
