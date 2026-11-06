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
    "NODE_OPTIONS", "MISE_GLOBAL_CONFIG_FILE", "MISE_SYSTEM_CONFIG_FILE",
]
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
        "JAVA_TOOL_OPTIONS": f"-Duser.home={home}",
        "MISE_CONFIG_DIR": str(home / ".config/mise"),
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


def _write(path: Path, text: str) -> None:
    """Write a file in the scratch home, replacing (not following) anything planted there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        path.unlink()
    with open(path, "x", encoding="utf-8") as out:
        out.write(text)


def _mise_tools(env: dict[str, str], real: Path) -> dict:
    candidates = [env.get("MISE_GLOBAL_CONFIG_FILE"), env.get("MISE_CONFIG_DIR")
                  and str(Path(env["MISE_CONFIG_DIR"]) / "config.toml"),
                  str(real / ".config/mise/config.toml")]
    for candidate in filter(None, candidates):
        try:
            tools = tomllib.loads(Path(candidate).read_text(encoding="utf-8")).get("tools")
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            continue
        return tools if isinstance(tools, dict) else {}
    return {}


def _version(value: object) -> str | list[str] | None:
    if isinstance(value, dict):
        value = value.get("version")
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
        return value
    return None


def _carry_versions(env: dict[str, str], real: Path, home: Path) -> None:
    """Copy the owner's global runtime versions, without mise's [env] and other settings."""
    try:
        _write(home / ".tool-versions", (real / ".tool-versions").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        pass
    tools = {name: v for name, raw in _mise_tools(env, real).items() if (v := _version(raw))}
    if tools:
        # JSON strings and lists of strings are valid TOML values and quoted keys.
        _write(home / ".config/mise/config.toml", "[tools]\n" + "".join(
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
        (scratch / "home").mkdir(parents=True, exist_ok=True)
        (scratch / "no-gh").mkdir(exist_ok=True)
    except OSError as exc:
        print(f"error: can't use {scratch}: {exc}", file=sys.stderr)
        return 1

    env = dict(os.environ)
    real = Path(env.get("HOME") or Path.home())
    try:
        _carry_versions(env, real, scratch / "home")
        # The Android Gradle plugin would otherwise download a pinned SDK into the kept
        # ANDROID_HOME, which is the owner's real SDK.
        _write(scratch / "home/.gradle/gradle.properties", "android.builder.sdkDownload=false\n")
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
