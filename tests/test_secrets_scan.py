import json
import re
import subprocess
from pathlib import Path

from conftest import SCRIPTS, run_script

# Built at run time so this file never holds a real-looking secret (the repo's guardrail
# blocks writing one).
AWS = "AKIA" + "Q" * 16
AWS_FIXTURE = "AKIA" + "Z" * 16
STRIPE = "sk_" + "live_" + "a1" * 12
GITHUB = "ghp" + "_" + "b2" * 18
OPENAI = "sk-" + "proj-" + "c3" * 12
PASSWORD = "S3cret" + "Passw0rd"


def scan(repo):
    result = run_script("secrets_scan", repo)
    assert result.returncode == 0, result.stderr
    return result, json.loads(result.stdout)


def test_finds_secrets_without_printing_them(make_repo):
    repo = make_repo({
        "src/config.js": f'const key = "{AWS}";\n',
        ".env": f"STRIPE_SECRET={STRIPE}\nDB_PASSWORD=changeme\nAPI_URL=https://x.test\n"
                "TOKEN_REF=${OTHER}\n",
        "crlf.py": f"x = 1\r\ntoken = '{GITHUB}'\r\n",
        "tests/fixtures/keys.js": f'"{AWS_FIXTURE}"\n',
        "deploy/db.yaml": f"url: postgres://admin:{PASSWORD}@db:5432/app\n",
        "node_modules/lib/x.js": f'"{AWS}"\n',
        ".gitignore": ".env.local\n",
    })
    (repo / "img.png").write_bytes(b"\x89PNG\x00\x00" + AWS.encode())
    (repo / "big.js").write_text("x" * 1_100_000 + f'\n"{AWS}"\n', encoding="utf-8")
    (repo / "latin1.js").write_bytes(b"caf\xe9 " + AWS.encode())
    subprocess.run(["git", "add", "img.png", "big.js", "latin1.js"], cwd=repo, check=True)
    (repo / ".env.local").write_text(f"OPENAI_KEY={OPENAI}\n", encoding="utf-8")

    result, found = scan(repo)
    got = {(f["path"], f["line"], f["pattern"], f["committed"], f["severity"]) for f in found}
    assert got == {
        ("src/config.js", 1, "aws-access-key-id", True, "critical"),
        (".env", 1, "stripe-live-key", True, "critical"),
        (".env", 2, "env-assignment", True, "low"),
        ("crlf.py", 2, "github-token", True, "critical"),
        ("tests/fixtures/keys.js", 1, "aws-access-key-id", True, "low"),
        ("deploy/db.yaml", 1, "url-credentials", True, "high"),
        (".env.local", 1, "openai-project-key", False, "low"),
    }
    assert all(f["length"] > 0 for f in found)
    for value in (AWS, AWS_FIXTURE, STRIPE, GITHUB, OPENAI, PASSWORD, "changeme"):
        assert value not in result.stdout + result.stderr
        assert value[:6] not in result.stdout


def test_clean_repo_and_bad_input(make_repo, tmp_path):
    repo = make_repo({"src/a.js": "const url = 'https://example.test/api';\n"})
    assert scan(repo)[1] == []

    plain = tmp_path / "plain dir"
    plain.mkdir()
    result = run_script("secrets_scan", plain)
    assert result.returncode == 1 and "Traceback" not in result.stderr


def test_guardrail_patterns_stay_in_sync():
    rule = (Path(__file__).resolve().parent.parent
            / ".claude/hookify/sdlc-secret-values.md").read_text(encoding="utf-8")
    guardrail = re.search(r"pattern: \((.*)\)\s*$", rule, re.M)[1]
    patterns = json.loads((SCRIPTS / "secret_patterns.json").read_text(encoding="utf-8"))
    ours = "|".join(p["regex"] for p in patterns["patterns"] if p.get("guardrail"))
    assert ours == guardrail


def test_values_decide_severity_and_every_hit_on_a_line_counts(make_repo):
    real = "Zq9" + "TxW2vLp8"
    repo = make_repo({
        ".env": f"EXAMPLE_STRIPE_SECRET={real}\nPASSWORD=$ecret!{real}\nREF=${{OTHER}}\n",
        "dist/app.min.js": 'var a="sk-' + "x" * 40 + f'",b="{AWS}";\n',
        "assets/blob.txt": "data:" + "akia" + "q" * 16 + "\n",
        "locked.js": f'"{AWS}"\n',
    })
    (repo / "locked.js").chmod(0)
    try:
        result, found = scan(repo)
    finally:
        (repo / "locked.js").chmod(0o644)
    got = {(f["path"], f["line"], f["pattern"], f["severity"]) for f in found}
    assert (".env", 1, "env-assignment", "high") in got
    assert (".env", 2, "env-assignment", "high") in got
    assert not any(f["path"] == ".env" and f["line"] == 3 for f in found)
    assert ("dist/app.min.js", 1, "aws-access-key-id", "critical") in got
    assert not any(f["path"] == "assets/blob.txt" for f in found)
    assert "Traceback" not in result.stderr


def test_only_whole_placeholders_count_as_placeholders():
    import sys
    sys.path.insert(0, str(SCRIPTS))
    from secrets_scan import is_placeholder

    for value in ("<redacted>", "<your", "<your api key>", "${OTHER}", "$(cmd)", "changeme",
                  "xxxx", "XXXXXXXX", "sk-" + "x" * 20, "AKIA" + "X" * 16, "your_api_key",
                  "example", "sk_" + "live_" + "x" * 20):
        assert is_placeholder(value), value
    for value in ("Pr0dPass<redacted>", "<redacted>tail9f2", "AKIAQ3J5ZP" + "xxxx",
                  "realexample9Key", "dummy" + "12345Zq", "Zq9TxW2vLp8"):
        assert not is_placeholder(value), value


def test_env_files_inside_ignored_folders_are_scanned(make_repo):
    real = "Zq9" + "TxW2vLp8"
    repo = make_repo({"src/a.js": "", ".gitignore": "secrets/\ndeploy/local/\n"})
    (repo / "secrets").mkdir()
    (repo / "secrets/.env").write_text(f"API_TOKEN={real}\n", encoding="utf-8")
    (repo / "deploy/local").mkdir(parents=True)
    (repo / "deploy/local/.env.prod").write_text(f"DB_PASSWORD={real}\n", encoding="utf-8")
    (repo / ".env.template").write_text("API_KEY=<your api key>\n", encoding="utf-8")
    _, found = scan(repo)
    got = {(f["path"], f["committed"]) for f in found}
    assert ("secrets/.env", False) in got and ("deploy/local/.env.prod", False) in got
    assert all(f["severity"] == "low" for f in found if f["path"] == ".env.template")
