import shutil
import subprocess

from conftest import run_script

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
