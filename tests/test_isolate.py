import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import isolate
import pytest
from conftest import SCRIPTS, run_script

WINDOWS = os.name == "nt"
windows_only = pytest.mark.skipif(not WINDOWS, reason="Windows-only behaviour")


def _bash() -> str:
    """Git Bash on Windows: a bare `bash` finds WSL's in System32 before anything on PATH."""
    if not WINDOWS:
        return "bash"
    exec_path = subprocess.run(["git", "--exec-path"], capture_output=True, text=True,
                               check=True).stdout.strip()
    return str(Path(exec_path).parents[2] / "usr" / "bin" / "bash.exe")


BASH = _bash()
# Builtins only: started from PowerShell, Git's usr/bin (with `env`) isn't on PATH.
DUMP_ENV = 'for n in $(compgen -e); do printf "%s=%s\\0" "$n" "${!n}"; done'

ISOLATE_LINE = (
    'ISO="$(python3 -I "<PLUGIN>/scripts/isolate.py" "<SCRATCH>")" && eval "$ISO" || exit 1;'
)


def isolated_env(scratch: Path, env: dict) -> dict:
    """Run isolate.py's output in bash, the way the agents do, and return the environment."""
    command = shlex.join([sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(scratch)])
    script = f'eval "$({command})"; {DUMP_ENV}'
    out = subprocess.run([BASH, "-c", script], env=env, capture_output=True, check=True).stdout
    return dict(item.split("=", 1) for item in out.decode().split("\0") if "=" in item)


def bash_path(env: dict) -> str:
    """PATH as bash holds it before isolation (Git Bash rewrites it into /c/... form)."""
    return subprocess.run([BASH, "-c", 'printf %s "$PATH"'], env=env, capture_output=True,
                          text=True, check=True).stdout


def run_fallback(scratch: Path, env: dict) -> subprocess.CompletedProcess:
    """Run isolate.py with the descriptor-relative calls switched off, as on Windows."""
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import isolate; "
            "isolate.DIR_FD = False; sys.exit(isolate._main(sys.argv[2:]))")
    return subprocess.run([sys.executable, "-I", "-c", code, str(SCRIPTS), str(scratch)],
                          env=env, capture_output=True, text=True, encoding="utf-8")


def link_folder(target: Path, link: Path) -> None:
    """A junction on Windows: it needs no privilege, so it's what planted code there would use."""
    if WINDOWS:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def symlink_or_skip(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link)
    except OSError as exc:
        if WINDOWS and getattr(exc, "winerror", None) == 1314:
            pytest.skip("creating a symlink on Windows needs Developer Mode or admin")
        raise


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
    for gone in ("GITHUB_TOKEN", "NPM_TOKEN", "MY_API_KEY", "AWS_SECRET_ACCESS_KEY",
                 "DB_PASSWORD", "SSH_AUTH_SOCK"):
        assert gone not in got, gone
    # Set, not unset: gh would otherwise use a login stored in Credential Manager or Keychain.
    assert got["GH_TOKEN"] == got["GH_ENTERPRISE_TOKEN"] == "isolated-no-token"
    assert got["KEEP_ME"] == "1"


def test_existing_toolchain_homes_are_kept(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    # Not /opt/...: Git Bash would rewrite that into its install folder on the way to Python.
    rustup, pyenv = str(tmp_path / "opt" / "rustup"), str(tmp_path / "opt" / "pyenv")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h"),
           "RUSTUP_HOME": rustup, "PYENV_ROOT": pyenv}
    got = isolated_env(scratch, env)
    assert got["RUSTUP_HOME"] == rustup and got["PYENV_ROOT"] == pyenv


def test_refuses_a_scratch_it_cant_use_safely(tmp_path):
    spaced = tmp_path / "has space"
    spaced.mkdir()
    result = run_script("isolate", spaced)
    assert result.returncode == 1 and "whitespace" in result.stderr
    assert "Traceback" not in result.stderr

    # A double quote can't be in a Windows file name.
    odd = tmp_path / ("x$(touch${IFS}pwned)`id`'qz" if WINDOWS
                      else "x$(touch${IFS}pwned)`id`'q\"z")
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
    before = bash_path(env) if WINDOWS else path
    got = isolated_env(scratch, env)
    for gone in ("PNPM_HOME", "BUN_INSTALL", "UV_CACHE_DIR", "POETRY_CONFIG_DIR",
                 "NPM_CONFIG_USERCONFIG", "MAVEN_USER_HOME", "VIRTUAL_ENV", "CONDA_PREFIX",
                 "CONDA_DEFAULT_ENV", "PYTHONHOME"):
        assert gone not in got, gone
    assert got["PATH"] == before
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
        "NVM_HOME": f"{real}/AppData/Roaming/nvm", "NVM_SYMLINK": f"{real}/nodejs",
        "PYENV": f"{real}/.pyenv/pyenv-win", "PYENV_HOME": f"{real}/.pyenv/pyenv-win",
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


@pytest.mark.skipif(WINDOWS, reason="Git Bash rewrites a HOME of / into the Git install "
                    "folder; test_points_into_compares_windows_paths covers Windows drive roots")
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
                 "MISE_GLOBAL_CONFIG_FILE"):
        assert gone not in got, gone
    assert got["MISE_SYSTEM_CONFIG_FILE"] != "/etc/m.toml"
    props = (scratch / "home/.gradle/gradle.properties").read_text(encoding="utf-8")
    assert "android.builder.sdkDownload=false" in props


def test_more_ca_variables_are_kept(tmp_path):
    real = tmp_path / "real"
    scratch = tmp_path / "s"
    scratch.mkdir()
    # On Windows both npm spellings are one variable, so only one can be set.
    kept = {k: f"{real}/ca.pem" for k in (
        *([] if WINDOWS else ["npm_config_cafile"]), "NPM_CONFIG_CAFILE", "GIT_SSL_CAINFO",
        "CARGO_HTTP_CAINFO", "AWS_CA_BUNDLE")}
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
        assert got["HOME"] == str(scratch / "home") and got["GH_TOKEN"] != "x", config

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
    symlink_or_skip(victim, scratch / "home/.tool-versions")
    result = run_script("isolate", scratch, env={"PATH": os.environ["PATH"], "HOME": str(real)})
    assert result.returncode == 1 and "symlink" in result.stderr
    assert victim.read_text(encoding="utf-8") == "keep"


def test_the_agents_isolation_line_fails_closed(tmp_path):
    spaced = tmp_path / "has space"
    spaced.mkdir()
    marker = tmp_path / "ran"
    line = ISOLATE_LINE.replace("<PLUGIN>", str(SCRIPTS.parent)).replace("<SCRATCH>", str(spaced))
    result = subprocess.run([BASH, "-c", f"{line} touch {shlex.quote(str(marker))}"],
                            capture_output=True)
    assert result.returncode != 0 and not marker.exists()


def test_symlinked_folders_in_the_scratch_home_stop_isolation(tmp_path):
    real = tmp_path / "real"
    victim = tmp_path / "victim-gradle"
    victim.mkdir()
    (victim / "gradle.properties").write_text("signing.password=keep\n", encoding="utf-8")
    scratch = tmp_path / "s"
    (scratch / "home").mkdir(parents=True)
    link_folder(victim, scratch / "home/.gradle")
    result = run_script("isolate", scratch, env={"PATH": os.environ["PATH"], "HOME": str(real)})
    assert result.returncode == 1 and "symlink" in result.stderr
    assert (victim / "gradle.properties").read_text(encoding="utf-8") == "signing.password=keep\n"

    scratch2 = tmp_path / "s2"
    scratch2.mkdir()
    real.mkdir()
    link_folder(real, scratch2 / "home")
    result = run_script("isolate", scratch2, env={"PATH": os.environ["PATH"], "HOME": str(real)})
    assert result.returncode == 1 and not (real / ".gradle").exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Windows has no FIFOs")
def test_fifo_version_files_are_skipped_not_read(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    os.mkfifo(real / ".tool-versions")
    scratch = tmp_path / "s"
    scratch.mkdir()
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(scratch)],
        env={"PATH": os.environ["PATH"], "HOME": str(real)}, capture_output=True, timeout=10,
    )
    assert result.returncode == 0
    assert not (scratch / "home/.tool-versions").exists()


def test_maven_config_dropped_and_mise_system_config_hidden(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h"),
                                 "MAVEN_CONFIG": "-s /r/settings.xml"})
    assert "MAVEN_CONFIG" not in got
    system = Path(got["MISE_SYSTEM_CONFIG_FILE"])
    assert system.is_relative_to(scratch) and not system.exists()


def test_xdg_config_home_mise_tools_are_carried(tmp_path):
    real = tmp_path / "real"
    xdg = tmp_path / "xdg"
    (xdg / "mise").mkdir(parents=True)
    (xdg / "mise/config.toml").write_text('[tools]\ngo = "1.23"\n', encoding="utf-8")
    scratch = tmp_path / "s"
    scratch.mkdir()
    isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real),
                           "XDG_CONFIG_HOME": str(xdg)})
    mise = (scratch / "home/.config/mise/config.toml").read_text(encoding="utf-8")
    assert tomllib.loads(mise) == {"tools": {"go": "1.23"}}


def test_proxy_flags_survive_but_proxy_passwords_do_not(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h"),
           "GRADLE_OPTS": "-Xmx1g -Dhttps.proxyHost=proxy.corp -Dhttps.proxyPort=8080 "
                          "-Dhttps.proxyPassword=hunter2",
           "MAVEN_OPTS": "-Dhttp.nonProxyHosts=localhost|*.corp -Dhttp.proxyUser=me"}
    got = isolated_env(scratch, env)
    home = scratch / "home"
    flags = got["JAVA_TOOL_OPTIONS"].split()
    assert flags[0] == f"-Duser.home={home}"
    assert sorted(flags[1:]) == sorted([
        "-Dhttps.proxyHost=proxy.corp", "-Dhttps.proxyPort=8080",
        "-Dhttp.nonProxyHosts=localhost|*.corp",
    ])


def test_planted_links_anywhere_at_the_top_of_the_scratch_home_stop_isolation(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    for planted in (".m2", ".npmrc", ".netrc", ".config/pip"):
        scratch = tmp_path / f"s{planted.replace('/', '-')}"
        (scratch / "home/.config").mkdir(parents=True)
        link_folder(real, scratch / "home" / planted)
        result = run_script("isolate", scratch,
                            env={"PATH": os.environ["PATH"], "HOME": str(real)})
        assert result.returncode == 1 and "symlink" in result.stderr, planted


def test_odd_proxy_values_are_skipped_and_system_proxies_carried(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h"),
           "JAVA_OPTS": '-Dhttps.proxyHost="a b" -Djava.net.useSystemProxies=true'}
    got = isolated_env(scratch, env)
    assert '"' not in got["JAVA_TOOL_OPTIONS"]
    assert "-Djava.net.useSystemProxies=true" in got["JAVA_TOOL_OPTIONS"].split()


def test_mise_conf_d_tools_are_carried_and_system_dir_hidden(tmp_path):
    real = tmp_path / "real"
    (real / ".config/mise/conf.d").mkdir(parents=True)
    (real / ".config/mise/conf.d/10-go.toml").write_text('[tools]\ngo = "1.23"\n', "utf-8")
    (real / ".config/mise/conf.d/20-env.toml").write_text('[env]\nTOKEN = "x"\n', "utf-8")
    (real / ".config/mise/config.toml").write_text('[tools]\nnode = "20"\n', "utf-8")
    scratch = tmp_path / "s"
    scratch.mkdir()
    got = isolated_env(scratch, {"PATH": os.environ["PATH"], "HOME": str(real)})
    mise = (scratch / "home/.config/mise/config.toml").read_text(encoding="utf-8")
    assert tomllib.loads(mise) == {"tools": {"go": "1.23", "node": "20"}}
    assert Path(got["MISE_SYSTEM_DIR"]).is_relative_to(scratch)
    assert not Path(got["MISE_SYSTEM_DIR"]).exists()


def test_a_second_run_in_the_same_scratch_works(tmp_path):
    real = tmp_path / "real"
    (real / ".config/mise").mkdir(parents=True)
    (real / ".tool-versions").write_text("nodejs 20\n", encoding="utf-8")
    (real / ".config/mise/config.toml").write_text('[tools]\nnode = "20"\n', encoding="utf-8")
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(real)}
    first = run_script("isolate", scratch, env=env)
    (scratch / "home/.npm/_cacache").mkdir(parents=True)
    (scratch / "home/.cargo/registry").mkdir(parents=True)
    second = run_script("isolate", scratch, env=env)
    assert first.returncode == 0 and second.returncode == 0, second.stderr
    assert first.stdout == second.stdout


def test_the_path_fallback_creates_the_home_folders(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / ".tool-versions").write_text("nodejs 20\n", encoding="utf-8")
    scratch = tmp_path / "s"
    scratch.mkdir()
    result = run_fallback(scratch, {**os.environ, "HOME": str(real)})
    assert result.returncode == 0, result.stderr
    home = scratch / "home"
    folders = ["", ".config"] + (["AppData/Roaming", "AppData/Local/Temp"] if WINDOWS else [])
    for folder in folders:
        assert (home / folder).is_dir(), folder
    assert (scratch / "no-gh").is_dir()
    assert (home / ".tool-versions").read_bytes() == b"nodejs 20\n"
    assert "sdkDownload=false" in (home / ".gradle/gradle.properties").read_text("utf-8")


def test_the_path_fallback_refuses_planted_links(tmp_path):
    real = tmp_path / "real"
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("keep", encoding="utf-8")
    planted = ["home", "home/.config", "home/.gradle"] + (
        ["home/AppData", "home/AppData/Local/Temp/x"] if WINDOWS else [])
    for n, where in enumerate(planted):
        scratch = tmp_path / f"s{n}"
        (scratch / where).parent.mkdir(parents=True, exist_ok=True)
        link_folder(victim, scratch / where)
        result = run_fallback(scratch, {**os.environ, "HOME": str(real)})
        assert result.returncode == 1 and result.stdout == "", where
        assert result.stderr.startswith("error:") and "symlink" in result.stderr, where
        assert "Traceback" not in result.stderr, where
        assert sorted(p.name for p in victim.iterdir()) == ["keep.txt"], where


@windows_only
def test_windows_profile_variables_move_into_the_scratch_home(tmp_path):
    real = tmp_path / "real"
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "SYSTEMROOT": os.environ["SYSTEMROOT"],
           "HOME": str(real), "USERPROFILE": str(real),
           "APPDATA": str(real / "AppData/Roaming"), "LOCALAPPDATA": str(real / "AppData/Local"),
           "TEMP": str(real / "AppData/Local/Temp"), "TMP": str(real / "AppData/Local/Temp")}
    got = isolated_env(scratch, env)
    home = scratch / "home"
    assert got["USERPROFILE"] == str(home)
    assert got["APPDATA"] == str(home / "AppData" / "Roaming")
    assert got["LOCALAPPDATA"] == str(home / "AppData" / "Local")
    temp = str(home / "AppData" / "Local" / "Temp")
    assert got["TEMP"] == got["TMP"] == got["TMPDIR"] == temp
    assert got["HOMEDRIVE"] + got["HOMEPATH"] == str(home)
    for key in ("APPDATA", "LOCALAPPDATA", "TEMP"):
        assert Path(got[key]).is_dir(), key


@windows_only
def test_windows_profile_paths_and_any_case_secrets_are_dropped(tmp_path):
    real = tmp_path / "Real"
    roaming = tmp_path / "roaming elsewhere"
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {"PATH": os.environ["PATH"], "SYSTEMROOT": os.environ["SYSTEMROOT"],
           "HOME": str(real), "USERPROFILE": str(real), "APPDATA": str(roaming),
           "OneDrive": str(real / "OneDrive"),
           "Tool_Dir": str(real).lower().replace("\\", "/") + "/tools",
           "Npm_Prefix": f"D:\\elsewhere;{roaming}\\npm",
           "MyApi_Token": "x", "Keep_Me": "D:\\data"}
    before = bash_path(env)
    got = isolated_env(scratch, env)
    for gone in ("OneDrive", "Tool_Dir", "Npm_Prefix", "MyApi_Token"):
        assert gone not in got, gone
    assert got["Keep_Me"] == "D:\\data"
    assert got["PATH"] == before


def test_points_into_compares_windows_paths(monkeypatch):
    monkeypatch.setattr(isolate, "WINDOWS", True)
    root = r"C:\Users\X"
    assert isolate._points_into("c:/users/x/AppData/Local/pnpm", root)
    assert isolate._points_into(r"D:\tools;C:\USERS\X\.cargo\bin", root)
    assert isolate._points_into(r"C:\Users\X", root + "\\")
    assert not isolate._points_into(r"C:\Users\X2\y", root)
    assert isolate._points_into(r'"C:\Users\X\quoted"', root)
    assert isolate._points_into(r"\\?\C:\Users\X\long", root)
    assert isolate._points_into("//?/C:/Users/X/long", root)
    assert isolate._points_into(r"D:\t; C:\Users\X\a", root)
    assert isolate._points_into(r"\\?\UNC\srv\profiles\x\a", r"\\srv\profiles\x")
    for drive_root in ("C:\\", "C:", "\\", "//", "/"):
        assert not isolate._points_into(r"C:\anything", drive_root), drive_root


def test_git_sees_no_global_or_system_config(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    command = shlex.join([sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(scratch)])
    script = (f'ISO="$({command})" && eval "$ISO" || exit 1; '
              "git config --list --show-origin; git config --get-all credential.helper; true")
    result = subprocess.run([BASH, "-c", script], cwd=tmp_path, capture_output=True, text=True,
                            env={**os.environ, "HOME": str(tmp_path / "real")})
    assert result.returncode == 0, result.stderr
    assert not [line for line in result.stdout.splitlines() if line.startswith("file:")]
    assert "credential.helper" not in result.stdout


def test_isolation_that_cant_be_set_up_exits_with_a_clear_error(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    (scratch / "home").write_text("not a folder", encoding="utf-8")
    result = run_script("isolate", scratch, env={**os.environ, "HOME": str(tmp_path / "real")})
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.startswith("error:") and len(result.stderr.splitlines()) == 1
    assert "Traceback" not in result.stderr


def test_the_descriptor_path_is_used_where_cpython_supports_it(monkeypatch):
    # CPython lists os.rename, never os.replace, in supports_dir_fd; both take dir_fd.
    monkeypatch.setattr(os, "supports_dir_fd", {os.open, os.mkdir, os.rename, os.unlink})
    monkeypatch.setattr(os, "O_DIRECTORY", 0o200000, raising=False)
    monkeypatch.setattr(os, "O_NOFOLLOW", 0o400000, raising=False)
    assert isolate._dir_fd()


@pytest.mark.skipif(WINDOWS, reason="Windows environment values are UTF-16, never stray bytes")
def test_undecodable_environment_bytes_dont_break_isolation(tmp_path):
    scratch = tmp_path / "s"
    scratch.mkdir()
    env = {b"PATH": os.environb[b"PATH"], b"HOME": str(tmp_path / "h").encode(),
           b"JAVA_HOME": b"/opt/jdk-\xff", b"LC_ALL": b"C"}
    result = subprocess.run([sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(scratch)],
                            env=env, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert b"/opt/jdk-\xff" in result.stdout


@pytest.mark.skipif(WINDOWS, reason="Windows Python has no descriptor-relative calls")
def test_the_descriptor_path_is_on_for_this_posix_python():
    assert isolate.DIR_FD
