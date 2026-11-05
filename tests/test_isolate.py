import os
import shlex
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS, run_script


def isolated_env(scratch: Path, env: dict) -> dict:
    """Run isolate.py's output in bash, the way the agents do, and return the environment."""
    command = shlex.join([sys.executable, str(SCRIPTS / "isolate.py"), str(scratch)])
    script = f'eval "$({command})"; env -0'
    out = subprocess.run(["bash", "-c", script], env=env, capture_output=True, check=True).stdout
    return dict(item.split("=", 1) for item in out.decode().split("\0") if "=" in item)


def test_home_caches_and_credentials_move_into_scratch(tmp_path):
    real = tmp_path / "real home"
    scratch = tmp_path / "scratch-1"
    scratch.mkdir()
    env = {
        "PATH": os.environ["PATH"], "HOME": str(real),
        "GH_TOKEN": "x", "GITHUB_TOKEN": "x", "NPM_TOKEN": "x", "MY_API_KEY": "x",
        "AWS_SECRET_ACCESS_KEY": "x", "DB_PASSWORD": "x", "SSH_AUTH_SOCK": "/tmp/agent",
        "KEEP_ME": "1",
    }
    got = isolated_env(scratch, env)
    home = scratch / "home"
    assert got["HOME"] == str(home) and home.is_dir()
    for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "CARGO_HOME", "GOPATH",
                "GOMODCACHE", "GRADLE_USER_HOME", "COMPOSER_HOME", "npm_config_cache"):
        assert got[key].startswith(str(home)), key
    assert got["JAVA_TOOL_OPTIONS"] == f"-Duser.home={home}"
    assert got["RUSTUP_HOME"] == str(real / ".rustup")
    assert got["PYENV_ROOT"] == str(real / ".pyenv")
    assert got["GH_CONFIG_DIR"] == str(scratch / "no-gh")
    assert got["GIT_CONFIG_GLOBAL"] == "/dev/null" and got["GIT_CONFIG_NOSYSTEM"] == "1"
    assert got["GIT_TERMINAL_PROMPT"] == "0"
    for gone in ("GH_TOKEN", "GITHUB_TOKEN", "NPM_TOKEN", "MY_API_KEY", "AWS_SECRET_ACCESS_KEY",
                 "DB_PASSWORD", "SSH_AUTH_SOCK"):
        assert gone not in got, gone
    assert got["KEEP_ME"] == "1"


def test_existing_toolchain_homes_are_kept(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h"),
           "RUSTUP_HOME": "/opt/rustup", "PYENV_ROOT": "/opt/pyenv"}
    got = isolated_env(scratch, env)
    assert got["RUSTUP_HOME"] == "/opt/rustup" and got["PYENV_ROOT"] == "/opt/pyenv"


def test_refuses_a_scratch_it_cant_use_safely(tmp_path):
    spaced = tmp_path / "has space"
    spaced.mkdir()
    result = run_script("isolate", spaced)
    assert result.returncode == 1 and "whitespace" in result.stderr
    assert "Traceback" not in result.stderr

    odd = tmp_path / "x$(touch${IFS}pwned)`id`'q\"z"
    odd.mkdir()
    got = isolated_env(odd, {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h")})
    assert got["HOME"] == str(odd / "home")
    assert not Path("pwned").exists() and not (tmp_path / "pwned").exists()
