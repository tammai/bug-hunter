import subprocess
import sys
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts" / "v1"


def test_vendored_contracts_match_manifest():
    # CONTRACTS.md (Distribution) requires this drift check in every consumer.
    result = subprocess.run(
        [sys.executable, str(CONTRACTS / "contracts.py"), "vendor-check", str(CONTRACTS)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("ok:")
