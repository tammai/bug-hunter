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
- **git reads far more than its config files from the environment:** `GIT_CONFIG_PARAMETERS`/`GIT_CONFIG_COUNT` inject config, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `SSH_ASKPASS` and `GIT_PROXY_COMMAND` run the owner's programs with their keys, and `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` point git at another repo (the target). Drop every inherited `GIT_*` but an allowlist (isolation's own `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, `GIT_TERMINAL_PROMPT`, `GIT_EDITOR`, `GIT_PAGER` and `GIT_SSH_COMMAND`, and the owner's `GIT_SSL_CAINFO`), not one name at a time. Then set `GIT_EDITOR=true` and `GIT_PAGER=cat` yourself: with none, git falls back to the owner's `VISUAL`/`EDITOR`/`PAGER`, then `vi`, which hangs a call with no terminal.
- **ssh ignores `HOME`:** it finds `~` through the password database, so git over ssh would use the owner's `~/.ssh/config`, keys and `known_hosts`. Isolation exports its own `GIT_SSH_COMMAND` (`ssh -F /dev/null -o IdentityFile=none -o IdentitiesOnly=yes -o IdentityAgent=none -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes -o BatchMode=yes`). `-F /dev/null` alone isn't enough, because the default `~/.ssh/id_*` and `known_hosts` still resolve. This covers git only: a plain `ssh` or `scp` started by target code still finds `~/.ssh`, the same as any read by absolute path.
- **Names bash can't unset:** `npm_config_//registry.npmjs.org/:_authToken` isn't a shell identifier, so `unset` refuses it, yet bash passes it to every child. No eval'd line can remove it. Isolation fails closed when such a name could carry a credential: a secret name, `GIT_*`, an always-dropped name, or a proxy URL with a password. The error names every such variable, with control and non-ASCII characters escaped so a name can't split the line or write terminal escapes. Odd names that only hold a path pass through, even into the home: Windows' `ProgramFiles(x86)`, JetBrains' `PyCharm Community Edition`, MSYS's `!C:`. An exported function (`BASH_FUNC_name%%`, or `BASH_FUNC_name()` from bash 4.2 with the 2014 patches) that isolation drops for holding a home path goes with `unset -f name`. That route needs two things: the value starts with `() {` (bash imports nothing else as a function), and the name couldn't carry a credential. A secret-named function (`get_token`, `git_author`, which matches `AUTH`) or a non-function `BASH_FUNC_` value goes through the credential gate like any odd name, so isolation stops. `unset -f` removes the `()` form only on a bash that imports it. Upstream bash 4.3+ and macOS's 3.2 don't, so there the raw variable reaches children; it can only be a harmless name holding a home path, which odd names may anyway.
- **Proxy credentials:** in any variable with `PROXY` in its name, everything between the scheme and the last `@` is cut, so a raw `/`, `@`, `,` or digits in a password leave nothing behind. This check runs even when the name is dropped for another reason, so an odd name can't slip through. Lists aren't split: no split can tell a separator from one inside a password (`http://u:4711,b://x@h` looks like two entries). A credentialed `GOPROXY=a,https://u:p@b|c` therefore keeps only `https://b|c`, losing the routing through `a` rather than keeping any of the password. When the cut part holds another `://`, the surviving host takes the scheme of its own entry: only a known one (`http`, `https`, `socks4`, `socks5` and their `a`/`h` forms) at the start of an entry, else none, so nothing from inside a password comes back as a scheme. An uncredentialed list is unchanged.
- **Check links through the opened descriptor** (`os.scandir(fd)`), not by `folder / name`, which walks the path again and may reach another folder.
- **Run the script with `python3 -I`:** an owner's `PYTHONHOME` or `PYTHONPATH` would break or hijack it.

On Windows (Git Bash running native Windows Python):

- **No descriptor-relative calls:** `os.supports_dir_fd` is empty and `O_DIRECTORY`/`O_NOFOLLOW` don't exist. The path fallback (`DIR_FD` false) creates each level, then `lstat`s it once, and refuses symlinks and any reparse point (a junction is always one). A link swapped in between that check and the write is followed; the owner accepted that gap.
- **Junctions need no privilege; symlinks do** (WinError 1314 without Developer Mode). Planted code would use a junction, and so do the tests (`_winapi.CreateJunction`).
- **The profile is several variables:** USERPROFILE (git, npm, ssh), APPDATA (gh, npm), LOCALAPPDATA (caches, installs), HOMEDRIVE+HOMEPATH. TEMP and TMP live under LOCALAPPDATA and many tools fail without them, so they move into the scratch home rather than being unset.
- **`os.environ` uppercases every name, but bash doesn't:** `unset ONEDRIVE` leaves `OneDrive`, and `MyApi_Token` survived a case-sensitive unset. Read `nt.environ`, compare names case-insensitively, and unset every spelling. Windows itself keeps only one of two spellings, so `npm_config_cafile` and `NPM_CONFIG_CAFILE` are one variable there.
- **Path comparisons:** compare `ntpath.normcase(ntpath.normpath(…))`, split on `;`, strip whitespace inside quotes too, expand 8.3 short names (`TAMMAI~1`) with `GetLongPathNameW` on the longest prefix that exists, and treat a drive root as matching nothing.
- **Unpaired surrogates:** a Windows environment value is UTF-16 and can hold one, which no UTF-8 output carries; check the output encodes before printing and name the variable, never its value.
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
