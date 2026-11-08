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

On Windows (Git Bash running native Windows Python):

- **No descriptor-relative calls:** `os.supports_dir_fd` is empty and `O_DIRECTORY`/`O_NOFOLLOW` don't exist. The path fallback (`DIR_FD` false) creates each level, then `lstat`s it, and refuses symlinks, junctions (`Path.is_junction`) and any reparse point. A link swapped in between that check and the write is followed; the owner accepted that gap.
- **Junctions need no privilege; symlinks do** (WinError 1314 without Developer Mode). Planted code would use a junction, and so do the tests (`_winapi.CreateJunction`).
- **The profile is several variables:** USERPROFILE (git, npm, ssh), APPDATA (gh, npm), LOCALAPPDATA (caches, installs), HOMEDRIVE+HOMEPATH. TEMP and TMP live under LOCALAPPDATA and many tools fail without them, so they move into the scratch home rather than being unset.
- **`os.environ` uppercases every name, but bash doesn't:** `unset ONEDRIVE` leaves `OneDrive`, and `MyApi_Token` survived a case-sensitive unset. Read `nt.environ`, compare names case-insensitively, and unset every spelling. Windows itself keeps only one of two spellings, so `npm_config_cafile` and `NPM_CONFIG_CAFILE` are one variable there.
- **Path comparisons:** compare `ntpath.normcase(ntpath.normpath(…))`, split on `;`, and treat a drive root as matching nothing.
- **Output encoding:** Python before 3.15 prints in the ANSI code page (cp1252), which garbles `naïve.py` and crashes on `tệp.py`. Every hunt and audit script switches stdout and stderr to UTF-8.
- **`bash` from Python is WSL's:** `CreateProcess` searches System32 before PATH. Tests take Git's bash from `git --exec-path`. Git Bash rewrites POSIX-looking values (`/opt/x`, a HOME of `/`) into its install folder when it starts a native program.
- **An empty `GH_CONFIG_DIR` doesn't log gh out:** gh still reads a login stored in Windows Credential Manager (or the macOS Keychain). Export `GH_TOKEN`/`GH_ENTERPRISE_TOKEN` as a placeholder, which gh prefers. The test suite filed real issues on Windows before its guard did the same.
- **`os.supports_dir_fd` lists `os.rename`, never `os.replace`:** checking `os.replace` turns the descriptor path off everywhere, silently, because the fallback passes the same tests.
- **TMPDIR too:** Git Bash's `/tmp` is the real `%LOCALAPPDATA%\Temp`, and MSYS tools and Python's `tempfile` read TMPDIR before TEMP.
- **Git for Windows' system config** (`C:\Program Files\Git\etc\gitconfig`) sets `credential.helper=manager`; `GIT_CONFIG_NOSYSTEM=1` keeps it out.
- **Out of reach of environment variables:** Windows OpenSSH's agent named pipe, Windows Credential Manager, DPAPI, and programs that find folders through the Known Folders API (.NET and NuGet, PowerShell).

What it still can't stop: code running with the owner's rights reading files by absolute path. Only a container fixes that.

**Browser mode (`isolate.py --browser`):**
- **Browsers:** Playwright's browsers stay where they are installed. `PLAYWRIGHT_BROWSERS_PATH` is set to the owner's real browsers folder, resolved before `HOME` and `LOCALAPPDATA` move, so the copy finds them.
- **No download:** `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` covers only install hooks; an explicit `playwright install` ignores it. So `PLAYWRIGHT_DOWNLOAD_HOST` points at a closed port (`127.0.0.1:9`), and any download fails instead of writing into the owner's folder.
- **The test is code:** the proxy confines the browser, not the test, which can open sockets itself. Only isolation contains it, which is why `/hunt` runs even its own Classify replays under `isolate.py --browser`.
- **Read-only, by rule only:** this is a read-only use of an owner folder by design, the same class as the runtime managers above. Nothing enforces it beyond the prompt rule "never `playwright install`": the CLI is run by path, so no shell function can intercept it.
- **No repo config:** `browser.py` writes its own Playwright config rather than using the repo's, because a repo config can start servers or a global setup.

From [2026-11-08-m-browser-mode](../../docs/sdlc/changes/2026-11-08-m-browser-mode.md).

The Windows section is from [2026-11-06-m-windows-isolation](../../docs/sdlc/changes/2026-11-06-m-windows-isolation.md).

From [2026-11-06-m-more-stacks](../../docs/sdlc/changes/2026-11-06-m-more-stacks.md).
