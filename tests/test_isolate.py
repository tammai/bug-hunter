import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

from conftest import SCRIPTS, run_script

ISOLATE_LINE = (
    'ISO="$(python3 -I "<PLUGIN>/scripts/isolate.py" "<SCRATCH>")" && eval "$ISO" || exit 1;'
)


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
    assert "VOLTA_HOME" not in got
    assert got["GOROOT"] == f"{real}/sdk/go"
    assert got["OTHER"] == "/usr/local/share"


def test_toolchain_locators_default_to_the_real_home(tmp_path):
    real = tmp_path / "real"
    scratch = tmp_path / "s"
    scratch.mkdir()
    got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real)})
    assert got["ASDF_DATA_DIR"] == str(real / ".asdf")
    assert got["MISE_DATA_DIR"] == str(real / ".local/share/mise")
    assert got["MISE_CONFIG_DIR"] == str(scratch / "home/.config/mise")
    assert "VOLTA_HOME" not in got
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


def test_repo_files_cant_install_into_the_real_home(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h")})
    assert got["POETRY_VIRTUALENVS_CREATE"] == "true"
    for key in ("MISE_AUTO_INSTALL", "MISE_NOT_FOUND_AUTO_INSTALL", "MISE_EXEC_AUTO_INSTALL",
                "MISE_TASK_RUN_AUTO_INSTALL"):
        assert got[key] == "0", key


def test_java_android_and_ca_bundles_are_kept_and_java_options_dropped(tmp_path):
    real = tmp_path / "real"
    scratch = tmp_path / "s"
    scratch.mkdir()
    kept = {
        "JAVA_HOME": f"{real}/.jdks/temurin-21", "ANDROID_HOME": f"{real}/Library/Android/sdk",
        "ANDROID_SDK_ROOT": f"{real}/Library/Android/sdk", "SSL_CERT_FILE": f"{real}/corp-ca.pem",
        "NODE_EXTRA_CA_CERTS": f"{real}/corp-ca.pem", "REQUESTS_CA_BUNDLE": f"{real}/corp-ca.pem",
        "CURL_CA_BUNDLE": f"{real}/corp-ca.pem",
    }
    env = {"PATH": os.environ["PATH"], "HOME": str(real), **kept,
           "_JAVA_OPTIONS": "-Duser.home=/elsewhere", "JDK_JAVA_OPTIONS": "-Dx=1"}
    got = isolated_env(scratch, env)
    for key, value in kept.items():
        assert got[key] == value, key
    assert "_JAVA_OPTIONS" not in got and "JDK_JAVA_OPTIONS" not in got


def test_global_runtime_versions_come_along_without_mise_env_secrets(tmp_path):
    real = tmp_path / "real"
    (real / ".config/mise").mkdir(parents=True)
    (real / ".tool-versions").write_text("nodejs 20.11.0\nruby 3.3.0\n", encoding="utf-8")
    (real / ".config/mise/config.toml").write_text(
        '[tools]\nnode = "20"\npython = ["3.12", "3.11"]\n\n[env]\nAPI_TOKEN = "s3cret"\n',
        encoding="utf-8",
    )
    scratch = tmp_path / "s"
    scratch.mkdir()
    isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real)})
    home = scratch / "home"
    assert (home / ".tool-versions").read_text(encoding="utf-8") == "nodejs 20.11.0\nruby 3.3.0\n"
    mise = (home / ".config/mise/config.toml").read_text(encoding="utf-8")
    assert tomllib.loads(mise) == {"tools": {"node": "20", "python": ["3.12", "3.11"]}}
    assert "s3cret" not in mise


def test_a_root_like_home_drops_nothing(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    for home in ("/", "//"):
        got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": home,
                                     "OTHER": "/usr/local/share"})
        assert got["OTHER"] == "/usr/local/share", home


def test_jvm_and_node_option_variables_are_dropped_and_android_downloads_off(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h"),
           "MAVEN_OPTS": "-Dmaven.repo.local=/r", "MAVEN_ARGS": "-s /r/settings.xml",
           "GRADLE_OPTS": "-Dgradle.user.home=/r", "JAVA_OPTS": "-Duser.home=/r",
           "NODE_OPTIONS": "--require /r/hook.js",
           "MISE_GLOBAL_CONFIG_FILE": "/etc/mise.toml", "MISE_SYSTEM_CONFIG_FILE": "/etc/m.toml"}
    got = isolated_env(scratch, env)
    for gone in ("MAVEN_OPTS", "MAVEN_ARGS", "GRADLE_OPTS", "JAVA_OPTS", "NODE_OPTIONS",
                 "MISE_GLOBAL_CONFIG_FILE", "MISE_SYSTEM_CONFIG_FILE"):
        assert gone not in got, gone
    props = (scratch / "home/.gradle/gradle.properties").read_text(encoding="utf-8")
    assert "android.builder.sdkDownload=false" in props


def test_more_ca_variables_are_kept(tmp_path):
    real = tmp_path / "real"
    scratch = tmp_path / "s"
    scratch.mkdir()
    kept = {k: f"{real}/ca.pem" for k in (
        "npm_config_cafile", "NPM_CONFIG_CAFILE", "GIT_SSL_CAINFO", "CARGO_HTTP_CAINFO",
        "AWS_CA_BUNDLE")}
    got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real), **kept})
    for key, value in kept.items():
        assert got[key] == value, key


def test_odd_or_unreadable_version_files_never_stop_isolation(tmp_path):
    real = tmp_path / "real"
    (real / ".config/mise").mkdir(parents=True)
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(real), "GH_TOKEN": "x"}
    for config in ('tools = "x"\n', "[tools\n", b"\xff\xfe", '[tools]\nnode = 20\n'):
        path = real / ".config/mise/config.toml"
        path.write_bytes(config if isinstance(config, bytes) else config.encode())
        got = isolated_env(scratch, env)
        assert got["HOME"] == str(scratch / "home") and "GH_TOKEN" not in got, config

    tool_versions = real / ".tool-versions"
    tool_versions.write_text("nodejs 20\n", encoding="utf-8")
    tool_versions.chmod(0)
    try:
        got = isolated_env(scratch, env)
    finally:
        tool_versions.chmod(0o644)
    assert got["HOME"] == str(scratch / "home")


def test_table_form_and_custom_location_mise_tools_are_carried(tmp_path):
    real = tmp_path / "real"
    custom = tmp_path / "elsewhere" / "mise.toml"
    custom.parent.mkdir(parents=True)
    custom.write_text('[tools]\nnode = { version = "20" }\nruby = "3.3"\n', encoding="utf-8")
    scratch = tmp_path / "s"
    scratch.mkdir()
    isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real),
                           "MISE_GLOBAL_CONFIG_FILE": str(custom)})
    mise = (scratch / "home/.config/mise/config.toml").read_text(encoding="utf-8")
    assert tomllib.loads(mise) == {"tools": {"node": "20", "ruby": "3.3"}}


def test_planted_symlinks_in_the_scratch_home_are_not_written_through(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / ".tool-versions").write_text("nodejs 20\n", encoding="utf-8")
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    scratch = tmp_path / "s"
    (scratch / "home").mkdir(parents=True)
    os.symlink(victim, scratch / "home/.tool-versions")
    isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real)})
    assert victim.read_text(encoding="utf-8") == "keep"
    assert (scratch / "home/.tool-versions").read_text(encoding="utf-8") == "nodejs 20\n"


def test_the_agents_isolation_line_fails_closed(tmp_path):
    spaced = tmp_path / "has space"
    spaced.mkdir()
    marker = tmp_path / "ran"
    line = ISOLATE_LINE.replace("<PLUGIN>", str(SCRIPTS.parent)).replace("<SCRATCH>", str(spaced))
    result = subprocess.run(["bash", "-c", f"{line} touch {shlex.quote(str(marker))}"],
                            capture_output=True)
    assert result.returncode != 0 and not marker.exists()
