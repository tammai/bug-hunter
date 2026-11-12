"""Print shell code that keeps an agent's tools off the owner's home, environments and secrets."""

import argparse
import json
import ntpath
import os
import re
import shlex
import stat
import sys
import tomllib
from pathlib import Path

# Variables that commonly hold a secret; unset so neither the target's code nor an install
# can read them.
SECRET_NAME = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|CREDENTIAL|AUTH)", re.I
)
# An active virtualenv or conda env would make Poetry install into the owner's environment;
# JVM and Node option variables can override user.home, the Maven or Gradle home, or preload a
# script; custom mise config files would bring back their [env] secrets.
ALWAYS_UNSET = [
    "SSH_AUTH_SOCK", "GOOGLE_APPLICATION_CREDENTIALS", "NETRC",
    "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "PYTHONHOME",
    "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "JAVA_OPTS", "MAVEN_OPTS", "MAVEN_ARGS", "GRADLE_OPTS",
    "MAVEN_CONFIG", "NODE_OPTIONS", "MISE_GLOBAL_CONFIG_FILE",
]
JVM_OPTION_VARS = ["JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "JAVA_OPTS",
                   "MAVEN_OPTS", "GRADLE_OPTS"]
# Proxy routing survives the JVM option variables being dropped, so Maven and Gradle still
# work behind a corporate proxy; proxy users and passwords never do.
PROXY_FLAG = re.compile(
    r"-D(?:(?:https?|ftp)\.(?:proxyHost|proxyPort|nonProxyHosts)|socksProxy(?:Host|Port)"
    r"|java\.net\.useSystemProxies)=\S+"
)
# Kept as they are when set: SDKs and JDKs often live under the home, and a corporate CA
# bundle is what lets installs through a TLS-inspecting proxy.
KEEP_IF_SET = [
    "GOROOT", "JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "PIP_CERT", "npm_config_cafile", "NPM_CONFIG_CAFILE", "GIT_SSL_CAINFO",
    "CARGO_HTTP_CAINFO", "AWS_CA_BUNDLE",
    # nvm-windows and pyenv-win
    "NVM_HOME", "NVM_SYMLINK", "PYENV", "PYENV_HOME",
]
WINDOWS = os.name == "nt"
# Opening each folder relative to its parent's descriptor leaves no gap for a link to be swapped
# in. Windows Python has none of these calls, so there the checks go by path instead.
def _dir_fd() -> bool:
    # CPython lists os.rename, never os.replace, in supports_dir_fd; both take dir_fd.
    return (hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW")
            and {os.open, os.mkdir, os.rename, os.unlink} <= os.supports_dir_fd)


DIR_FD = _dir_fd()


def _toolchains(env: dict[str, str], real: Path) -> dict[str, str]:
    """Where installed runtimes live, so node, go, ruby and java still resolve once HOME moves."""
    data = Path(env.get("XDG_DATA_HOME") or real / ".local/share")
    # Volta is left out: its shims fetch a pinned Node into VOLTA_HOME, which must not be the
    # real home.
    defaults = {
        "RUSTUP_HOME": real / ".rustup",
        "PYENV_ROOT": real / ".pyenv",
        "ASDF_DATA_DIR": real / ".asdf",
        "MISE_DATA_DIR": data / "mise",
        "NVM_DIR": real / ".nvm",
        "SDKMAN_DIR": real / ".sdkman",
    }
    found = {key: env.get(key) or str(path) for key, path in defaults.items()}
    found.update({key: env[key] for key in KEEP_IF_SET if env.get(key)})
    return found


def _win_path(path: str) -> str:
    path = path.strip().strip('"')
    # Long-path forms name the same folder: \\?\C:\x is C:\x, \\?\UNC\srv\p is \\srv\p.
    for prefix, plain in (("\\\\?\\UNC\\", "\\\\"), ("//?/UNC/", "//"), ("\\\\?\\", ""),
                          ("//?/", "")):
        if path.upper().startswith(prefix):
            path = plain + path[len(prefix):]
            break
    return ntpath.normcase(ntpath.normpath(path)).rstrip("\\") if path else ""


def _points_into(value: str, root: Path | str) -> bool:
    if not WINDOWS:
        prefix = str(root).rstrip("/")
        return any(
            part == prefix or part.startswith(prefix + "/") for part in value.split(os.pathsep)
        )
    prefix = _win_path(str(root))
    # A drive root (C:\, \) holds everything, so it can't mark a value as the owner's.
    if not ntpath.splitdrive(prefix)[1]:
        return False
    return any(
        part == prefix or part.startswith(prefix + "\\")
        for part in map(_win_path, value.split(";"))
    )


def _lookup(env: dict[str, str]) -> dict[str, str]:
    """env for reading: Windows names are case-insensitive, so read them uppercased there."""
    return {k.upper(): v for k, v in env.items()} if WINDOWS else env


def _shared_caches(cache: Path) -> dict[str, str]:
    """Download caches every agent in a run can share: content-checked and safe to fill at once."""
    # Left per agent: Gradle's user home holds its daemons, Maven's local repository has no
    # locking by default, Cargo's home holds the config.toml every build obeys, and Bun
    # hardlinks installs to its cache. uv and pnpm are told to copy or clone out of the
    # cache, since a hardlink would let one agent's edit to an installed file reach the rest.
    return {
        "npm_config_cache": str(cache / "npm"),
        "npm_config_store_dir": str(cache / "pnpm-store"),
        "npm_config_package_import_method": "clone-or-copy",
        "YARN_CACHE_FOLDER": str(cache / "yarn"),
        "YARN_GLOBAL_FOLDER": str(cache / "yarn-berry"),
        "UV_CACHE_DIR": str(cache / "uv"),
        "UV_LINK_MODE": "clone" if sys.platform == "darwin" else "copy",
        "PIP_CACHE_DIR": str(cache / "pip"),
        "POETRY_CACHE_DIR": str(cache / "poetry"),
        "COMPOSER_CACHE_DIR": str(cache / "composer"),
        "GOMODCACHE": str(cache / "go-mod"),
        "GOCACHE": str(cache / "go-build"),
        "BUNDLE_USER_CACHE": str(cache / "bundler"),
    }


def _plan(scratch: Path, env: dict[str, str],
          cache: Path | None = None) -> tuple[list[str], dict[str, str]]:
    """The variables to unset and to export."""
    view = _lookup(env)
    real = Path(view.get("HOME") or Path.home())
    home = scratch / "home"
    keep = _toolchains(view, real)
    exports = {
        **keep,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "CARGO_HOME": str(home / ".cargo"),
        "GOPATH": str(home / "go"),
        "GOMODCACHE": str(home / "go/pkg/mod"),
        "GRADLE_USER_HOME": str(home / ".gradle"),
        "COMPOSER_HOME": str(home / ".composer"),
        "npm_config_cache": str(home / ".npm"),
        # Java reads user.home from the password database, not HOME, so Maven would still find
        # ~/.m2/settings.xml and its server credentials without this.
        "JAVA_TOOL_OPTIONS": " ".join([f"-Duser.home={home}", *_proxy_flags(view)]),
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
        # Never created: points mise away from /etc/mise and its [env].
        "MISE_SYSTEM_CONFIG_FILE": str(scratch / "no-mise-system.toml"),
        "MISE_SYSTEM_DIR": str(scratch / "no-mise-system"),
        # A repo's mise.toml or .tool-versions must not install runtimes into the real home.
        "MISE_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_AUTO_INSTALL": "0",
        "MISE_EXEC_AUTO_INSTALL": "0",
        "MISE_TASK_RUN_AUTO_INSTALL": "0",
        # Overrides a committed poetry.toml that turns venv creation off.
        "POETRY_VIRTUALENVS_CREATE": "true",
        "POETRY_VIRTUALENVS_IN_PROJECT": "true",
        # Relative on purpose: each project's gems land in its own folder in the copy, and a
        # later `bundle exec` finds them because it reads the same variable.
        "BUNDLE_PATH": "vendor/bundle",
        "RUSTUP_AUTO_INSTALL": "0",
        "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
        "GH_CONFIG_DIR": str(scratch / "no-gh"),
        # Set rather than unset: gh prefers these to a login stored in Windows Credential
        # Manager or the macOS Keychain, which an empty config doesn't hide.
        "GH_TOKEN": "isolated-no-token",
        "GH_ENTERPRISE_TOKEN": "isolated-no-token",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    if cache is not None:
        exports.update(_shared_caches(cache))
    roots = [real]
    if WINDOWS:
        # A kept variable goes out under the name(s) the owner set it with, not uppercased.
        kept = {k.upper() for k in keep}
        present = {k.upper() for k in env}
        exports = {
            **{k: v for k, v in env.items() if k.upper() in kept},
            **{k: v for k, v in exports.items() if not (k in keep and k.upper() in present)},
        }
        # git, npm and ssh find their config through USERPROFILE, gh and npm through APPDATA,
        # caches and tool installs through LOCALAPPDATA. TEMP and TMP live under LOCALAPPDATA
        # and many tools fail without them, so they move rather than go.
        local = home / "AppData" / "Local"
        drive, rest = ntpath.splitdrive(str(home))
        exports.update({
            "USERPROFILE": str(home), "APPDATA": str(home / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(local), "HOMEDRIVE": drive, "HOMEPATH": rest,
            # Git Bash tools and Python's tempfile read TMPDIR first; /tmp is the real Temp.
            "TEMP": str(local / "Temp"), "TMP": str(local / "Temp"),
            "TMPDIR": str(local / "Temp"),
        })
        # Roaming profiles and redirected folders put these outside USERPROFILE.
        roots += [Path(view[k]) for k in ("USERPROFILE", "APPDATA", "LOCALAPPDATA") if view.get(k)]
    # Bash names are case-sensitive but Windows ones aren't, so there OneDrive must be unset as
    # OneDrive, and another spelling of an exported name would reach native tools beside it.
    fold = str.upper if WINDOWS else str
    exported = {fold(k) for k in exports}
    always = {fold(k) for k in ALWAYS_UNSET}
    # Shell profiles export tool paths (PNPM_HOME, UV_CACHE_DIR, NPM_CONFIG_USERCONFIG, …)
    # already expanded against the real home; moving HOME doesn't move them.
    into_home = {
        k for k, v in env.items()
        if fold(k) not in exported and fold(k) != "PATH" and str(real).strip("/")
        and any(_points_into(v, root) for root in roots)
    }
    secrets = {k for k in env if SECRET_NAME.search(k)}
    respelled = {k for k in env if fold(k) in exported and k not in exports}
    named = {k for k in env if fold(k) in always}
    unset = {
        k for k in (*ALWAYS_UNSET, *named, *into_home, *secrets, *respelled)
        if (k in respelled or fold(k) not in exported) and re.fullmatch(r"[A-Za-z_]\w*", k)
    }
    return sorted(unset), exports


def _proxy_flags(env: dict[str, str]) -> list[str]:
    flags: list[str] = []
    for key in JVM_OPTION_VARS:
        for flag in PROXY_FLAG.findall(env.get(key, "")):
            # A quoted value was split at a space; carrying half of it could stop Java starting.
            if flag not in flags and not set(flag) & set("\"'\\"):
                flags.append(flag)
    return flags


def _open_folder(scratch: Path, folder: Path) -> int:
    """Open folder under scratch, creating it one level at a time; refuse any symlink."""
    fd = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in folder.relative_to(scratch).parts:
            try:
                os.mkdir(part, dir_fd=fd)
            except FileExistsError:
                pass
            try:
                # Opening relative to the parent's descriptor with O_NOFOLLOW leaves no gap
                # between the check and the use for a link to be swapped in.
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except OSError as exc:
                raise OSError(f"{folder}: {part} is a symlink or not a folder; "
                              "refusing to write through it") from exc
            os.close(fd)
            fd = child
    except BaseException:
        os.close(fd)
        raise
    return fd


def _is_link(path: Path) -> bool:
    """A symlink, a junction or any other reparse point: each can lead out of scratch."""
    st = os.lstat(path)
    return (stat.S_ISLNK(st.st_mode) or path.is_junction()
            or bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT))


def _check_folder(scratch: Path, folder: Path) -> None:
    """The path fallback of _open_folder: create each level, then refuse a link at it."""
    # A link swapped in after the check would be followed; that needs code already running
    # in scratch, which environment isolation can't stop anyway.
    path = scratch
    for part in folder.relative_to(scratch).parts:
        path = path / part
        try:
            path.mkdir()
        except FileExistsError:
            pass
        if _is_link(path) or not path.is_dir():
            raise OSError(f"{folder}: {part} is a symlink, junction or not a folder; "
                          "refusing to write through it")


def _is_run_folder(folder: Path) -> bool:
    """Whether folder holds scratch.py's marker as a plain file, never a link to one."""
    try:
        return stat.S_ISREG(os.lstat(folder / ".bug-hunter-run").st_mode)
    except OSError:
        return False


def _make_folder(scratch: Path, folder: Path) -> None:
    if DIR_FD:
        os.close(_open_folder(scratch, folder))
    else:
        _check_folder(scratch, folder)


def _refuse_links(scratch: Path, folder: Path) -> None:
    """Refuse a symlink at any entry of folder: tools there would follow it out of scratch."""
    if not DIR_FD:
        _check_folder(scratch, folder)
        for entry in os.scandir(folder):
            if _is_link(Path(entry.path)):
                raise OSError(f"{entry.path} is a symlink or junction; refusing to use this home")
        return
    fd = _open_folder(scratch, folder)
    try:
        for name in os.listdir(fd):
            if os.path.islink(folder / name):
                raise OSError(f"{folder / name} is a symlink; refusing to use this home")
    finally:
        os.close(fd)


def _write(scratch: Path, path: Path, text: str) -> None:
    """Write a file under scratch atomically, never following a planted symlink."""
    if not DIR_FD:
        _write_by_path(scratch, path, text)
        return
    fd = _open_folder(scratch, path.parent)
    tmp = f".isolate-{os.getpid()}-{os.urandom(4).hex()}"
    try:
        out_fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644,
                         dir_fd=fd)
        try:
            with os.fdopen(out_fd, "w", encoding="utf-8") as out:
                out.write(text)
            # The rename replaces the name itself, so a symlink planted at the target is
            # replaced rather than followed.
            os.replace(tmp, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=fd)
            except OSError:
                pass
            raise
    finally:
        os.close(fd)


def _write_by_path(scratch: Path, path: Path, text: str) -> None:
    """The path fallback of _write."""
    _check_folder(scratch, path.parent)
    tmp = path.parent / f".isolate-{os.getpid()}-{os.urandom(4).hex()}"
    # O_EXCL refuses a link planted at the temp name; O_BINARY keeps the bytes as they came.
    out_fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                     0o644)
    try:
        with os.fdopen(out_fd, "w", encoding="utf-8", newline="") as out:
            out.write(text)
        # Replacing the name swaps out a link planted at the target rather than following it.
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _read(path: Path) -> str | None:
    """A regular file's text; None for anything else (missing, FIFO, device, unreadable)."""
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def _toml_tools(text: str | None) -> dict:
    if text is None:
        return {}
    try:
        tools = tomllib.loads(text).get("tools")
    except tomllib.TOMLDecodeError:
        return {}
    return tools if isinstance(tools, dict) else {}


def _mise_tools(env: dict[str, str], real: Path) -> dict:
    """The owner's global [tools]: conf.d files first, then the main config on top."""
    config_dir = Path(env.get("MISE_CONFIG_DIR") or Path(
        env.get("XDG_CONFIG_HOME") or real / ".config") / "mise")
    tools: dict = {}
    conf_d = config_dir / "conf.d"
    if conf_d.is_dir():
        for path in sorted(conf_d.glob("*.toml")):
            tools.update(_toml_tools(_read(path)))
    candidates = [
        env.get("MISE_GLOBAL_CONFIG_FILE"),
        env.get("MISE_CONFIG_DIR") and str(Path(env["MISE_CONFIG_DIR"]) / "config.toml"),
        env.get("XDG_CONFIG_HOME") and str(Path(env["XDG_CONFIG_HOME"]) / "mise/config.toml"),
        str(real / ".config/mise/config.toml"),
    ]
    for candidate in filter(None, candidates):
        text = _read(Path(candidate))
        if text is not None:
            tools.update(_toml_tools(text))
            break
    return tools


def _version(value: object) -> str | list[str] | None:
    if isinstance(value, dict):
        value = value.get("version")
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
        return value
    return None


def _carry_versions(env: dict[str, str], real: Path, scratch: Path) -> None:
    """Copy the owner's global runtime versions, without mise's [env] and other settings."""
    home = scratch / "home"
    tool_versions = _read(real / ".tool-versions")
    if tool_versions is not None:
        _write(scratch, home / ".tool-versions", tool_versions)
    tools = {name: v for name, raw in _mise_tools(env, real).items() if (v := _version(raw))}
    if tools:
        # JSON strings and lists of strings are valid TOML values and quoted keys.
        _write(scratch, home / ".config/mise/config.toml", "[tools]\n" + "".join(
            f"{json.dumps(name)} = {json.dumps(v)}\n" for name, v in tools.items()
        ))


def _browsers_dir(view: dict[str, str], real: Path) -> Path:
    """Playwright's browsers folder before isolation, as browser.py finds it."""
    # A copy of browser.browsers_dir: this script runs with -I, so it imports no neighbour.
    chosen = view.get("PLAYWRIGHT_BROWSERS_PATH")
    if chosen and chosen != "0":
        return Path(chosen)
    if WINDOWS:
        return Path(view.get("LOCALAPPDATA") or real / "AppData" / "Local") / "ms-playwright"
    if sys.platform == "darwin":
        return real / "Library" / "Caches" / "ms-playwright"
    return Path(view.get("XDG_CACHE_HOME") or real / ".cache") / "ms-playwright"


def _environ() -> dict[str, str]:
    if WINDOWS:
        # os.environ uppercases every name on Windows; bash, which evals the output, doesn't.
        import nt
        return dict(nt.environ)
    return dict(os.environ)


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; Git Bash reads UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch")
    parser.add_argument("--cache", help="the run's download cache, shared by its agents")
    parser.add_argument("--browser", action="store_true",
                        help="keep Playwright's installed browsers readable; downloads fail")
    args = parser.parse_args(argv)
    scratch = Path(args.scratch).resolve()
    if any(ch.isspace() for ch in str(scratch)):
        print("error: the scratch path has whitespace, which JAVA_TOOL_OPTIONS can't carry; "
              "use a mktemp -d path", file=sys.stderr)
        return 1
    cache = None
    if args.cache is not None:
        given = Path(args.cache)
        cache = given.parent.resolve() / given.name
        if any(ch.isspace() for ch in str(cache)):
            print("error: the cache path has whitespace; use the run folder scratch.py made",
                  file=sys.stderr)
            return 1
        # Only inside a run folder scratch.py made, so a wrong path can't point every
        # agent's downloads at the owner's own folders.
        if not _is_run_folder(cache.parent):
            print(f"error: the cache {cache} isn't in a run folder made by scratch.py",
                  file=sys.stderr)
            return 1
        try:
            # Created under its parent, so a symlink planted at the cache path is refused
            # rather than followed.
            _make_folder(cache.parent, cache)
            _refuse_links(cache.parent, cache)
        except OSError as exc:
            print(f"error: can't use the cache {cache}: {exc}", file=sys.stderr)
            return 1
    folders = ["home", "home/.config", "no-gh"]
    scanned = ["home", "home/.config"]
    if WINDOWS:
        folders += ["home/AppData/Roaming", "home/AppData/Local/Temp"]
        scanned += ["home/AppData", "home/AppData/Roaming", "home/AppData/Local",
                    "home/AppData/Local/Temp"]
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        for folder in folders:
            _make_folder(scratch, scratch / folder)
        for folder in scanned:
            _refuse_links(scratch, scratch / folder)
    except OSError as exc:
        print(f"error: can't use {scratch}: {exc}", file=sys.stderr)
        return 1

    env = _environ()
    view = _lookup(env)
    real = Path(view.get("HOME") or Path.home())
    try:
        _carry_versions(view, real, scratch)
        # The Android Gradle plugin would otherwise download a pinned SDK into the kept
        # ANDROID_HOME, which is the owner's real SDK.
        _write(scratch, scratch / "home/.gradle/gradle.properties",
               "android.builder.sdkDownload=false\n")
    except OSError as exc:
        print(f"error: can't prepare {scratch / 'home'}: {exc}", file=sys.stderr)
        return 1
    unset, exports = _plan(scratch, env, cache)
    if args.browser:
        # The owner's installed browsers, used where they are: HOME and LOCALAPPDATA move
        # into the scratch folder, where Playwright would find none. The skip variable only
        # covers install hooks; an explicit `playwright install` reads the download host,
        # which is pointed at a closed port so it fails rather than writing to the folder.
        exports["PLAYWRIGHT_BROWSERS_PATH"] = str(_browsers_dir(view, real))
        exports["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
        exports["PLAYWRIGHT_DOWNLOAD_HOST"] = "http://127.0.0.1:9"
    # Servers outlive the call that starts them; listing them on exit lets reap.py stop them.
    record = shlex.join([Path(sys.executable).as_posix(), "-I",
                         Path(__file__).with_name("reap.py").as_posix(), scratch.as_posix(),
                         "--record"])
    listing = f'j=$(jobs -p); [ -z "$j" ] || {record} $j > /dev/null 2>&1'
    # Agents start in the target repo; a cd chained into a backgrounded `&&` list never
    # reaches their own shell, so a relative write would land in the repo.
    home_dir = " || ".join(f"cd {shlex.quote(p.as_posix())}"
                           for p in (scratch / "copy", scratch))
    print("unset " + " ".join(unset) + "; export " + " ".join(
        f"{key}={shlex.quote(value)}" for key, value in exports.items()
    ) + f"; trap {shlex.quote(listing)} EXIT; {{ {home_dir}; }} 2> /dev/null;")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
