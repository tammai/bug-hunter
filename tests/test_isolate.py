import os
import shlex
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS, run_script


def isolated_env(scratch: Path, env: dict) -> dict:
    """Run isolate.py's output in bash, the way the agents do, and return the environment."""
    command = shlex.join([sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(scratch)])
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


def test_inherited_paths_into_the_real_home_are_dropped_but_toolchains_kept(tmp_path):
    real = tmp_path / "real"
    scratch = tmp_path / "s"
    scratch.mkdir()
    path = f"{real}/.cargo/bin{os.pathsep}{os.environ['PATH']}"
    env = {
        "PATH": path, "HOME": str(real),
        "PNPM_HOME": f"{real}/Library/pnpm", "BUN_INSTALL": f"{real}/.bun",
        "UV_CACHE_DIR": f"{real}/.cache/uv", "POETRY_CONFIG_DIR": f"{real}/.config/pypoetry",
        "NPM_CONFIG_USERCONFIG": f"{real}/.npmrc", "MAVEN_USER_HOME": f"{real}/.m2",
        "VIRTUAL_ENV": "/opt/venvs/app", "CONDA_PREFIX": "/opt/conda/envs/x",
        "CONDA_DEFAULT_ENV": "x", "PYTHONHOME": "/opt/py",
        "ASDF_DATA_DIR": f"{real}/.asdf", "VOLTA_HOME": f"{real}/.volta",
        "GOROOT": f"{real}/sdk/go", "OTHER": "/usr/local/share",
    }
    got = isolated_env(scratch, env)
    for gone in ("PNPM_HOME", "BUN_INSTALL", "UV_CACHE_DIR", "POETRY_CONFIG_DIR",
                 "NPM_CONFIG_USERCONFIG", "MAVEN_USER_HOME", "VIRTUAL_ENV", "CONDA_PREFIX",
                 "CONDA_DEFAULT_ENV", "PYTHONHOME"):
        assert gone not in got, gone
    assert got["PATH"] == path
    assert got["ASDF_DATA_DIR"] == f"{real}/.asdf"
    assert got["VOLTA_HOME"] == f"{real}/.volta"
    assert got["GOROOT"] == f"{real}/sdk/go"
    assert got["OTHER"] == "/usr/local/share"


def test_toolchain_locators_default_to_the_real_home(tmp_path):
    real = tmp_path / "real"
    scratch = tmp_path / "s"
    scratch.mkdir()
    got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real)})
    assert got["ASDF_DATA_DIR"] == str(real / ".asdf")
    assert got["MISE_DATA_DIR"] == str(real / ".local/share/mise")
    assert got["MISE_CONFIG_DIR"] == str(real / ".config/mise")
    assert got["VOLTA_HOME"] == str(real / ".volta")
    assert got["NVM_DIR"] == str(real / ".nvm")
    assert got["SDKMAN_DIR"] == str(real / ".sdkman")


def test_installs_stay_in_the_copy_and_off_the_keyring(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h")})
    assert got["POETRY_VIRTUALENVS_IN_PROJECT"] == "true"
    assert got["BUNDLE_PATH"] == "vendor/bundle"
    assert got["RUSTUP_AUTO_INSTALL"] == "0"
    assert got["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
