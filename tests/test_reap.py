import os
import shlex
import shutil
import subprocess
import sys

from conftest import SCRIPTS, run_script

# Resolved, not bare: Windows looks for a bare "bash" in System32 first, which is WSL's.
BASH = shutil.which("bash")


def alive(pid: str) -> bool:
    return subprocess.run([BASH, "-c", f"kill -0 {pid}"], capture_output=True).returncode == 0


def test_stops_what_agents_listed_and_ignores_the_rest(tmp_path):
    # json-server, B0 run 8: a hunter left the server it started running, so the scratch
    # folder couldn't be deleted. Agents list background PIDs in <their scratch>/bg.pids.
    scratch = tmp_path / "scratch dir"
    agent = scratch / "hunter-1"
    agent.mkdir(parents=True)
    started = subprocess.run(
        [BASH, "-c", 'sleep 300 > /dev/null 2>&1 & echo $! >> "$1/bg.pids"; echo $!', "_",
         agent.as_posix()],
        capture_output=True, text=True, check=True)
    pid = started.stdout.strip()
    assert alive(pid)
    with (agent / "bg.pids").open("a", encoding="utf-8") as f:
        f.write("1; touch hacked\n\n999999999\r\n")

    result = run_script("reap", scratch)
    assert result.returncode == 0, result.stderr
    assert not alive(pid)
    assert "stopped 1" in result.stdout
    assert not (scratch / "hacked").exists() and not (agent / "hacked").exists()

    assert run_script("reap", tmp_path / "missing").returncode == 0


def children(pid: str) -> list[str]:
    rows = subprocess.run([shutil.which("ps"), "-ef"], capture_output=True, text=True).stdout
    return [cols[1] for cols in (row.split() for row in rows.splitlines()[1:])
            if len(cols) > 2 and cols[2] == pid]


def test_stops_the_processes_under_a_listed_subshell(tmp_path):
    # json-server, B0 run 10: `cmd && node src/bin.ts … &` backgrounds a subshell, so `$!` is
    # the subshell; killing it left node serving on its port.
    agent = tmp_path / "hunter-1"
    agent.mkdir()
    started = subprocess.run(
        [BASH, "-c", '( sleep 300; true ) > /dev/null 2>&1 & echo $! >> "$1/bg.pids"; echo $!',
         "_", agent.as_posix()],
        capture_output=True, text=True, check=True)
    shell = started.stdout.strip()
    inner = []
    while not inner:
        inner = children(shell)

    assert run_script("reap", tmp_path).returncode == 0
    assert not alive(shell) and not any(alive(pid) for pid in inner)


def test_a_subshell_killed_before_reap_still_has_its_child_stopped(tmp_path):
    # An agent that kills the listed subshell itself orphans the child under PID 1, where
    # reap can no longer find it, unless the tree was recorded while the subshell lived.
    agent = tmp_path / "hunter-1"
    command = shlex.join([sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(agent)])
    script = (f'eval "$({command})"; ( sleep 300; true ) > /dev/null 2>&1 & s=$!; '
              'until ps -ef | awk -v p="$s" \'$3 == p {f = 1} END {exit !f}\'; do :; done; echo $s')
    shell = subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                           check=True).stdout.strip()
    inner = children(shell)
    assert inner
    subprocess.run([BASH, "-c", f"kill {shell}"], check=True)

    assert run_script("reap", tmp_path).returncode == 0
    assert not any(alive(pid) for pid in inner)


def test_tools_in_the_current_folder_are_never_run(tmp_path):
    # /hunt runs reap from the target repo's root, and Windows'
    # lookup tries the current folder first, so a committed ps.bat would run unisolated.
    repo = tmp_path / "target"
    repo.mkdir()
    marker = tmp_path / "ran"
    for name in ("ps", "kill"):
        for ext in (".bat", ".cmd"):
            (repo / f"{name}{ext}").write_text(f"@echo x > \"{marker}\"\r\n", encoding="utf-8")
    agent = tmp_path / "hunter-1"
    agent.mkdir()
    started = subprocess.run([BASH, "-c", "sleep 300 > /dev/null 2>&1 & echo $!"],
                             capture_output=True, text=True, check=True)
    pid = started.stdout.strip()
    (agent / "bg.pids").write_text(pid + "\n", encoding="utf-8")

    # Claude Code's shell sets this, which hides the lookup; other hosts don't.
    env = {k: v for k, v in os.environ.items()
           if k.upper() != "NODEFAULTCURRENTDIRECTORYINEXEPATH"}
    result = run_script("reap", tmp_path, cwd=repo, env=env)
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert not alive(pid)


def test_pid_lines_too_long_for_a_pid_are_skipped(tmp_path):
    agent = tmp_path / "hunter-1"
    agent.mkdir()
    (agent / "bg.pids").write_text("99999999999\n" + "9" * 5000 + "\n", encoding="utf-8")
    result = run_script("reap", tmp_path)
    assert result.returncode == 0, result.stderr
    assert "stopped 0" in result.stdout
