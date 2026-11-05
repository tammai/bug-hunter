import shutil
from pathlib import Path

from conftest import run_script

GOOD = """# Sort puts B10 before B2

## What happens
`backlog.py next` picks B10 first.

## Steps to reproduce
```
$ python3 backlog.py next backlog.md
B10
```

## Expected
B2.

## Root cause
`scripts/backlog.py`, `next_slice`, lines 40–44: sorts IDs as strings.
"""


def test_dir_is_outside_target_named_after_origin(make_repo, fake_gh, tmp_path):
    env, _ = fake_gh
    home = Path(env["HOME"])
    for origin in (
        "https://github.com/tammai/sdlc.git",
        "git@github.com:tammai/sdlc.git",
        "ssh://git@github.com/tammai/sdlc",
    ):
        repo = make_repo({"a.py": ""}, origin=origin)
        result = run_script("drafts", "dir", repo, env=env)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == str(home / ".bug-hunter" / "tammai-sdlc" / "drafts")
        assert str(repo) not in result.stdout
        shutil.rmtree(repo)

    repo = make_repo({"a.py": ""})
    result = run_script("drafts", "dir", repo, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(home / ".bug-hunter" / "my repö" / "drafts")


def test_next_number_sorts_numerically(tmp_path):
    drafts = tmp_path / "drafts ü"
    assert run_script("drafts", "next", drafts).stdout.strip() == "01"
    assert not drafts.exists()

    drafts.mkdir()
    assert run_script("drafts", "next", drafts).stdout.strip() == "01"
    for name in ("01.md", "09.md", ".DS_Store", "posted.json", "notes.md"):
        (drafts / name).write_text("x", encoding="utf-8")
    assert run_script("drafts", "next", drafts).stdout.strip() == "10"
    (drafts / "10.md").write_text("x", encoding="utf-8")
    (drafts / "2.md").write_text("x", encoding="utf-8")
    assert run_script("drafts", "next", drafts).stdout.strip() == "11"


def test_check_enforces_fixed_format(tmp_path):
    def check(text: str, name: str = "01.md"):
        path = tmp_path / name
        path.write_bytes(text.encode("utf-8"))
        return run_script("drafts", "check", path)

    assert check(GOOD).returncode == 0
    assert check(GOOD.replace("\n", "\r\n"), "crlf.md").returncode == 0

    no_title = check(GOOD.replace("# Sort puts B10 before B2\n", ""))
    assert no_title.returncode == 1 and "title" in no_title.stdout

    missing = check(GOOD.replace("## Expected\nB2.\n", ""))
    assert missing.returncode == 1 and "Expected" in missing.stdout

    swapped = GOOD.replace("## What happens", "## TMP").replace("## Expected", "## What happens")
    out_of_order = check(swapped.replace("## TMP", "## Expected"))
    assert out_of_order.returncode == 1 and "order" in out_of_order.stdout

    empty = check(GOOD.replace("B2.\n", ""))
    assert empty.returncode == 1 and "Expected" in empty.stdout and "empty" in empty.stdout

    no_output = check(GOOD.replace("```\n", ""))
    assert no_output.returncode == 1 and "code block" in no_output.stdout

    both = check(GOOD.replace("B2.\n", "").replace("```\n", ""))
    assert both.returncode == 1 and len(both.stdout.strip().splitlines()) == 2

    empty_file = check("", "empty.md")
    assert empty_file.returncode == 1

    gone = run_script("drafts", "check", tmp_path / "nope.md")
    assert gone.returncode == 1 and "Traceback" not in gone.stderr
