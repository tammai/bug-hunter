"""Print shell code that keeps an agent's tools off the owner's home, environments and secrets."""

import argparse
import os
import re
import shlex
import sys
from pathlib import Path

# Variables that commonly hold a secret; unset so neither the target's code nor an install
# can read them.
SECRET_NAME = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|CREDENTIAL|AUTH)", re.I
)
# An active virtualenv or conda env would make Poetry install into the owner's environment.
ALWAYS_UNSET = [
    "SSH_AUTH_SOCK", "GOOGLE_APPLICATION_CREDENTIALS", "NETRC",
    "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "PYTHONHOME",
]


def _toolchains(env: dict[str, str], real: Path) -> dict[str, str]:
    """Where installed runtimes live, so node, go, ruby and java still resolve once HOME moves."""
    data = Path(env.get("XDG_DATA_HOME") or real / ".local/share")
    config = Path(env.get("XDG_CONFIG_HOME") or real / ".config")
    defaults = {
        "RUSTUP_HOME": real / ".rustup",
        "PYENV_ROOT": real / ".pyenv",
        "ASDF_DATA_DIR": real / ".asdf",
        "MISE_DATA_DIR": data / "mise",
        "MISE_CONFIG_DIR": config / "mise",
        "VOLTA_HOME": real / ".volta",
        "NVM_DIR": real / ".nvm",
        "SDKMAN_DIR": real / ".sdkman",
    }
    found = {key: env.get(key) or str(path) for key, path in defaults.items()}
    if env.get("GOROOT"):
        found["GOROOT"] = env["GOROOT"]
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
        if k not in exports and k != "PATH" and real != Path("/") and _points_into(v, real)
    }
    secrets = {k for k in env if SECRET_NAME.search(k)}
    unset = {
        k for k in (*ALWAYS_UNSET, *into_home, *secrets)
        if k not in exports and re.fullmatch(r"[A-Za-z_]\w*", k)
    }
    return sorted(unset), exports


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

    unset, exports = _plan(scratch, dict(os.environ))
    print("unset " + " ".join(unset) + "; export " + " ".join(
        f"{key}={shlex.quote(value)}" for key, value in exports.items()
    ) + ";")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
