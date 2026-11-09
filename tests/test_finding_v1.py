import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import run_script
from drafts import problems

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts" / "v1" / "contracts.py"


def routed(path):
    """`contracts.py finding`'s verdict on one file."""
    # contracts.py prints "→", which Windows' default console code page can't encode.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, str(CONTRACTS), "finding", str(path)],
                            capture_output=True, text=True, encoding="utf-8", env=env)
    return result.returncode, result.stdout.strip()


STEPS = [
    {"command": "cat > backlog.md <<'EOF'\n$ B10\nB2\nEOF", "stdout": ""},
    {"command": "python3 backlog.py next backlog.md", "stdout": "B10\n"},
    {"command": "cat notes.md", "stdout": "```\n$ 5.00\n```\n"},
]

TEMPLATE = """# Sort puts B10 before B2
Severity: high

## What happens
`backlog.py next` picks B10 first.

## Steps to reproduce
Rendered from the Repro section.

## Repro (finding-v1)
```json
@@REPRO@@
```

## Expected
B2.

## Root cause
`scripts/backlog.py`, `next_slice`, lines 40–44: sorts IDs as strings.
"""

RENDERED_STEPS = """## Steps to reproduce
````
$ cat > backlog.md <<'EOF'
$ B10
B2
EOF
$ python3 backlog.py next backlog.md
B10
$ cat notes.md
```
$ 5.00
```
````
"""


def with_repro(steps):
    return TEMPLATE.replace("@@REPRO@@", json.dumps(steps))


DRAFT = with_repro(STEPS)


def write(tmp_path, repo, out, text, name="draft.md"):
    draft = tmp_path / name
    draft.write_text(text, encoding="utf-8")
    return run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft)


def test_render_writes_steps_from_the_json(tmp_path):
    draft = tmp_path / "draft ü.md"
    draft.write_text(DRAFT, encoding="utf-8")
    result = run_script("finding_v1", "render", "--draft", draft)
    assert result.returncode == 0, result.stderr
    text = draft.read_text(encoding="utf-8")
    assert RENDERED_STEPS in text
    assert "Rendered from the Repro section." not in text
    assert problems(text) == []
    assert run_script("finding_v1", "render", "--draft", draft).returncode == 0
    assert draft.read_text(encoding="utf-8") == text

    draft.write_text(DRAFT.replace("## Steps to reproduce\nRendered from the Repro section.\n\n",
                                   ""), encoding="utf-8")
    assert run_script("finding_v1", "render", "--draft", draft).returncode == 0
    assert draft.read_text(encoding="utf-8") == text

    draft.write_text(with_repro([{"command": "./progress", "stdout": "50%\r```\ndone\n"}]),
                     encoding="utf-8", newline="")
    assert run_script("finding_v1", "render", "--draft", draft).returncode == 0
    text = draft.read_text(encoding="utf-8")
    assert "````\n$ ./progress\n50%\n```\ndone\n````\n" in text
    assert problems(text) == []


def test_verified_draft_becomes_a_c6_finding(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    out = tmp_path / "findings ü"
    result = write(tmp_path, repo, out, DRAFT)
    assert result.returncode == 0, result.stderr
    path = out / "BH-0001.json"
    assert result.stdout.strip() == str(path)
    finding = json.loads(path.read_text(encoding="utf-8"))
    assert routed(path) == (0, "routed: BH-0001 → sdlc")
    assert finding["source"] == "bug-hunter"
    assert finding["class"] == "build-defect"
    assert finding["severity"] == "high"
    assert finding["criterion"] is None and finding["rule"] is None
    assert finding["observed"] == {"rebuild": "`backlog.py next` picks B10 first.",
                                   "reference": "not run: no --reference"}
    assert finding["verified_by"] == {"agent": "repro-verifier", "result": "reproduced"}
    assert finding["title"] == "Sort puts B10 before B2"
    assert RENDERED_STEPS in finding["draft"]
    assert finding["repro"] == {"runner": "cli", "steps": STEPS}

    printed = tmp_path / "printed.md"
    printed.write_text(with_repro(
        [*STEPS, {"command": "./cli", "stdout": "Set before running: `API_KEY`\n"}]),
        encoding="utf-8")
    assert run_script("finding_v1", "render", "--draft", printed).returncode == 0
    result = run_script("finding_v1", "write", "--repo", repo, "--out", tmp_path / "printed",
                        "--draft", printed)
    assert result.returncode == 0, result.stderr
    assert "env" not in json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))["repro"]

    live = DRAFT.replace("Severity: high", "Set before running: `BASE` (the dev URL), `BOB_AUTH` "
                         "(a header that logs in as bob)\nSeverity: Medium")
    result = write(tmp_path, repo, out, live, "live.md")
    assert result.returncode == 0, result.stderr
    second = json.loads((out / "BH-0002.json").read_text(encoding="utf-8"))
    assert second["severity"] == "medium"
    assert second["repro"]["env"] == ["BASE", "BOB_AUTH"]

    for name in ("BH-0009.json", "BH-0000000005.json", "notes.json", "BH-7.txt"):
        (out / name).write_text("{}", encoding="utf-8")
    result = write(tmp_path, repo, out, DRAFT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(out / "BH-0010.json")
    assert (out / "BH-0009.json").read_text(encoding="utf-8") == "{}"


def test_oracle_expected_sets_the_class(make_repo, tmp_path):
    lock = {"criteria": [{"id": "F-TSK-01.AC2", "feature": "F-TSK-01", "file": "f.md",
                          "level": 2}]}
    repo = make_repo({"spec/domain.md": "# Domain rules\n\n## Roles and permissions\nx\n",
                      "spec/criteria.lock.json": json.dumps(lock)})
    out = tmp_path / "out"
    cases = [
        ("", "B2, per F-TSK-01.AC2.", "build-defect", "F-TSK-01.AC2", None, "sdlc"),
        ("", "Only a member (domain.md §Roles and permissions).", "build-defect", None,
         "domain.md §Roles and permissions", "sdlc"),
        ("Oracle: spec-gap\n", "No criterion or rule covers this.", "spec-gap", None, None,
         "rspec"),
    ]
    for header, expected, klass, criterion, rule, route in cases:
        text = DRAFT.replace("Severity: high\n", "Severity: high\n" + header)
        draft = tmp_path / "oracle.md"
        draft.write_text(text.replace("## Expected\nB2.", "## Expected\n" + expected),
                         encoding="utf-8")
        result = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft,
                            "--oracle", repo / "spec")
        assert result.returncode == 0, result.stderr
        path = Path(result.stdout.strip())
        finding = json.loads(path.read_text(encoding="utf-8"))
        assert (finding["class"], finding["criterion"], finding["rule"], finding["route"]) == \
            (klass, criterion, rule, route), expected
        assert finding["verified_by"]["result"] == "reproduced"
        assert routed(path) == (0, f"routed: {finding['id']} → {route}")

    for expected in ("B2, per F-TSK-01.AC9.", "It should be B2."):
        draft.write_text(DRAFT.replace("## Expected\nB2.", "## Expected\n" + expected),
                         encoding="utf-8")
        result = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft,
                            "--oracle", repo / "spec")
        assert result.returncode == 1 and result.stderr.startswith("error:"), expected
        assert "Traceback" not in result.stderr
    assert len(list(out.iterdir())) == 3


def test_refuses_without_severity_or_repro_or_outside_out(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    out = tmp_path / "out"
    bad = {
        "no severity": DRAFT.replace("Severity: high\n", ""),
        "bad severity": DRAFT.replace("Severity: high", "Severity: critical"),
        "no repro": DRAFT.split("## Repro (finding-v1)")[0] + "## Expected\nB2.\n",
        "not JSON": TEMPLATE.replace("@@REPRO@@", "[{command: ls}]"),
        "empty": with_repro([]),
        "extra key": with_repro([{**STEPS[1], "exit": 0}]),
        "not a string": with_repro([{"command": "ls", "stdout": 3}]),
        "blank command": with_repro([{"command": " \nls", "stdout": ""}]),
        "prompt kept": with_repro([{"command": "$ ls", "stdout": ""}]),
        "severity on the next line": DRAFT.replace("Severity: high", "Severity:\n\nhigh"),
        "two Steps sections": DRAFT.replace("## Expected", "## Steps to reproduce\n```\n"
                                            "$ rm -rf x\n```\n\n## Expected"),
        "two blocks": TEMPLATE.replace("@@REPRO@@", json.dumps(STEPS) + "\n```\n```json\n[]"),
    }
    for why, text in bad.items():
        for command in ("write", "render"):
            draft = tmp_path / "bad.md"
            draft.write_text(text, encoding="utf-8")
            args = ["--repo", repo, "--out", out] if command == "write" else []
            result = run_script("finding_v1", command, *args, "--draft", draft)
            assert result.returncode == 1, (why, command)
            assert result.stdout == "" and result.stderr.startswith("error:"), why
            assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr
            assert draft.read_text(encoding="utf-8") == text
    assert not out.exists()

    inside = write(tmp_path, repo, repo / "findings", DRAFT)
    assert inside.returncode == 1 and inside.stderr.startswith("error:")
    assert not (repo / "findings").exists()

    (tmp_path / "bad.md").write_bytes(b"# t\n\xff\xfe\n")
    unreadable = run_script("finding_v1", "write", "--repo", repo, "--out", out,
                            "--draft", tmp_path / "bad.md")
    assert unreadable.returncode == 1 and unreadable.stderr.startswith("error:")
    assert "Traceback" not in unreadable.stderr


def test_case_insensitive_names_never_hang(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    out = tmp_path / "out"
    out.mkdir()
    (out / "bh-0001.json").write_text("{}", encoding="utf-8")
    draft = tmp_path / "d.md"
    draft.write_text(DRAFT, encoding="utf-8")
    command = [sys.executable, str(ROOT / "scripts" / "finding_v1.py"), "write",
               "--repo", str(repo), "--out", str(out), "--draft", str(draft)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(out / "BH-0002.json")

    for name in ("BH-999999999.json", "BH-99999999999999999999.json"):
        (out / name).write_text("{}", encoding="utf-8")
        full = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              timeout=30)
        assert full.returncode == 1 and full.stderr.startswith("error:"), name
        assert "Traceback" not in full.stderr
        (out / name).unlink()
