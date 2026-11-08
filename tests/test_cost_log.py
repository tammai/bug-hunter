import json
import subprocess
import sys
from pathlib import Path

from conftest import run_script

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts" / "v1" / "contracts.py"
HUNTER = ["--stage", "hunt", "--agent", "bug-hunter", "--tier", "session", "--wall-s", "61.5",
          "--turns", "14", "--tokens-total", "123456", "--result", "findings: 2"]


def test_appends_valid_c7_lines(tmp_path):
    log = tmp_path / "run ü" / "cost.jsonl"
    log.parent.mkdir()
    assert run_script("cost_log", "--file", log, *HUNTER).returncode == 0
    result = run_script("cost_log", "--file", log, "--stage", "verify", "--agent",
                        "repro-verifier", "--tier", "session", "--wall-s", "9", "--turns", "3",
                        "--tokens-total", "none", "--result", "reproduces")
    assert result.returncode == 0, result.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["plugin"] == "bug-hunter"
    assert (first["stage"], first["agent"], first["wall_s"], first["turns"]) == \
        ("hunt", "bug-hunter", 61.5, 14)
    assert first["tokens_in"] is None and first["tokens_out"] is None
    assert first["tokens_total"] == 123456
    assert json.loads(lines[1])["tokens_total"] is None
    check = subprocess.run([sys.executable, str(CONTRACTS), "cost", str(log)],
                           capture_output=True, text=True, encoding="utf-8")
    assert check.returncode == 0, check.stdout
    assert json.loads(check.stdout)["hunt"]["runs"] == 1


def test_bad_input_writes_nothing(tmp_path):
    log = tmp_path / "cost.jsonl"
    for swap in (("--wall-s", "61.5", "-1"), ("--turns", "14", "many"),
                 ("--tokens-total", "123456", "-5")):
        args = list(HUNTER)
        args[args.index(swap[0]) + 1] = swap[2]
        result = run_script("cost_log", "--file", log, *args)
        assert result.returncode == 1, swap
        assert result.stderr.startswith("error:") and "Traceback" not in result.stderr
    assert not log.exists()

    missing = run_script("cost_log", "--file", tmp_path / "no dir" / "cost.jsonl", *HUNTER)
    assert missing.returncode == 1 and missing.stderr.startswith("error:")
    assert "Traceback" not in missing.stderr
