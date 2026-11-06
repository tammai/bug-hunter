"""Print shell code that keeps an agent's tools off the owner's home, environments and secrets."""

import argparse
import json
import os
import re
import shlex
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
]


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


def _points_into(value: str, root: Path) -> bool:
    prefix = str(root).rstrip("/")
    return any(
        part == prefix or part.startswith(prefix + "/") for part in value.split(os.pathsep)
    )


def _plan(scratch: Path, env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """The variables to unset and to export."""
    real = Path(env.get("HOME") or Path.home())
    home = scratch / "home"
    keep = _toolchains(env, real)
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
        "JAVA_TOOL_OPTIONS": " ".join([f"-Duser.home={home}", *_proxy_flags(env)]),
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
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    # Shell profiles export tool paths (PNPM_HOME, UV_CACHE_DIR, NPM_CONFIG_USERCONFIG, …)
    # already expanded against the real home; moving HOME doesn't move them.
    into_home = {
        k for k, v in env.items()
        if k not in exports and k != "PATH" and str(real).strip("/") and _points_into(v, real)
    }
    secrets = {k for k in env if SECRET_NAME.search(k)}
    unset = {
        k for k in (*ALWAYS_UNSET, *into_home, *secrets)
        if k not in exports and re.fullmatch(r"[A-Za-z_]\w*", k)
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


def _refuse_links(scratch: Path, folder: Path) -> None:
    """Refuse a symlink at any entry of folder: tools there would follow it out of scratch."""
    fd = _open_folder(scratch, folder)
    try:
        for name in os.listdir(fd):
            if os.path.islink(folder / name):
                raise OSError(f"{folder / name} is a symlink; refusing to use this home")
    finally:
        os.close(fd)


def _write(scratch: Path, path: Path, text: str) -> None:
    """Write a file under scratch atomically, never following a planted symlink."""
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


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch")
    args = parser.parse_args(argv)
    scratch = Path(args.scratch).resolve()
    if any(ch.isspace() for ch in str(scratch)):
        print("error: the scratch path has whitespace, which JAVA_TOOL_OPTIONS can't carry; "
              "use a mktemp -d path", file=sys.stderr)
        return 1
    try:
        scratch.mkdir(parents=True, exist_ok=True)
        for folder in ("home", "home/.config", "no-gh"):
            os.close(_open_folder(scratch, scratch / folder))
        _refuse_links(scratch, scratch / "home")
        _refuse_links(scratch, scratch / "home/.config")
    except OSError as exc:
        print(f"error: can't use {scratch}: {exc}", file=sys.stderr)
        return 1

    env = dict(os.environ)
    real = Path(env.get("HOME") or Path.home())
    try:
        _carry_versions(env, real, scratch)
        # The Android Gradle plugin would otherwise download a pinned SDK into the kept
        # ANDROID_HOME, which is the owner's real SDK.
        _write(scratch, scratch / "home/.gradle/gradle.properties",
               "android.builder.sdkDownload=false\n")
    except OSError as exc:
        print(f"error: can't prepare {scratch / 'home'}: {exc}", file=sys.stderr)
        return 1
    unset, exports = _plan(scratch, env)
    print("unset " + " ".join(unset) + "; export " + " ".join(
        f"{key}={shlex.quote(value)}" for key, value in exports.items()
    ) + ";")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
