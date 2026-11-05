"""Print shell code that moves an agent's home, caches and credentials out of the owner's reach."""

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
ALWAYS_UNSET = ["SSH_AUTH_SOCK", "GOOGLE_APPLICATION_CREDENTIALS", "NETRC"]


def _exports(scratch: Path, env: dict[str, str]) -> dict[str, str]:
    real_home = Path(env.get("HOME") or Path.home())
    home = scratch / "home"
    return {
        # Toolchains installed under the real home keep working once HOME moves.
        "RUSTUP_HOME": env.get("RUSTUP_HOME") or str(real_home / ".rustup"),
        "PYENV_ROOT": env.get("PYENV_ROOT") or str(real_home / ".pyenv"),
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
        "GH_CONFIG_DIR": str(scratch / "no-gh"),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


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

    names = (k for k in os.environ if SECRET_NAME.search(k) and re.fullmatch(r"[A-Za-z_]\w*", k))
    unset = sorted({*ALWAYS_UNSET, *names})
    exports = _exports(scratch, dict(os.environ))
    print("unset " + " ".join(unset) + "; export " + " ".join(
        f"{key}={shlex.quote(value)}" for key, value in exports.items()
    ) + ";")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
