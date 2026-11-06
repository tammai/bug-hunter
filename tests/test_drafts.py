import json
import os
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
        want = home / ".bug-hunter" / "github.com" / "tammai" / "sdlc" / "drafts"
        assert result.stdout.strip() == str(want)
        assert str(repo) not in result.stdout
        shutil.rmtree(repo)

    repo = make_repo({"a.py": ""})
    result = run_script("drafts", "dir", repo, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(home / ".bug-hunter" / "local" / "my repö" / "drafts")


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


def test_dir_names_never_collide_or_escape(make_repo, fake_gh):
    env, _ = fake_gh
    seen = set()
    for origin in (
        "https://github.com/acme-web/api.git",
        "https://github.com/acme/web-api.git",
        "https://gitlab.example/acme/web-api.git",
        "ssh://git@gitlab.example:2222/group/sub/web-api.git",
    ):
        repo = make_repo({"a.py": ""}, origin=origin)
        result = run_script("drafts", "dir", repo, env=env)
        assert result.returncode == 0, result.stderr
        seen.add(result.stdout.strip())
        shutil.rmtree(repo)
    assert len(seen) == 4

    for origin in ("git@github.com:../../etc.git", "https://github.com/a/./b"):
        repo = make_repo({"a.py": ""}, origin=origin)
        result = run_script("drafts", "dir", repo, env=env)
        assert result.returncode == 1 and "Traceback" not in result.stderr
        shutil.rmtree(repo)

    repo = make_repo({"a.py": ""})
    no_git = {**env, "PATH": str(Path(env["HOME"]) / "no bin")}
    result = run_script("drafts", "dir", repo, env=no_git)
    assert result.returncode == 1 and "git" in result.stderr and "Traceback" not in result.stderr


def test_check_rejects_empty_title_and_ignores_headings_in_output(tmp_path):
    path = tmp_path / "01.md"
    path.write_text(GOOD.replace("# Sort puts B10 before B2", "#   "), encoding="utf-8")
    result = run_script("drafts", "check", path)
    assert result.returncode == 1 and "title" in result.stdout

    fenced = GOOD.replace("B10\n```", "B10\n## Expected\n## Root cause\n```")
    path.write_text(fenced, encoding="utf-8")
    result = run_script("drafts", "check", path)
    assert result.returncode == 0, result.stdout


LIVE = """# Order total accepts a negative quantity

Set before running: `BASE` (the dev or UAT URL), `ALICE_AUTH` (a normal user's login header).

## What happens
A negative quantity makes a negative total.

## Steps to reproduce
```
$ curl -sS -X POST "$BASE/api/orders" -H "$ALICE_AUTH" -d '{"qty": -1}'
{"total": -10}
$ curl -sS "$BASE/api/me" -H "Authorization: Bearer invented-bad-token"
{"error": "unauthorized"}
```

## Expected
400 for a quantity below 1.

## Root cause
`src/orders.js`, `createOrder`, lines 10–14: no lower bound on `qty`.
"""


def test_live_drafts_hide_host_and_credentials(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin="https://github.com/acme/shop.git")
    home = tmp_path / "home dir"
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    targets = home / ".bug-hunter" / "github.com" / "acme" / "shop" / "targets.json"
    targets.parent.mkdir(parents=True)
    targets.write_text(json.dumps({"uat": {"url": "https://uat.acme.test:8443/api", "accounts": {
        "alice": {"Authorization": "Bearer Zq8Wx7CeTk41", "Cookie": "sid=Mm3Nn4Pp5"}}}}),
        encoding="utf-8")

    def check(text: str, target: str = "uat"):
        path = tmp_path / "draft.md"
        path.write_text(text, encoding="utf-8")
        return run_script("drafts", "check", path, "--repo", repo, "--target", target, env=env)

    assert check(LIVE).returncode == 0, check(LIVE).stdout
    assert check(LIVE, "http://localhost:3000").returncode == 0
    bad = [
        LIVE.replace('"$BASE/api/orders"', '"https://uat.acme.test:8443/api/orders"'),
        LIVE.replace('-H "$ALICE_AUTH"', '-H "X-Bug-Hunter-Account: alice"'),
        LIVE.replace("invented-bad-token", "Zq8Wx7CeTk41"),
        LIVE.replace('-H "$ALICE_AUTH"', '-H "Cookie: sid=Mm3Nn4Pp5"'),
        LIVE.replace("Set before running: `BASE` (the dev or UAT URL), ", "Set before running: "),
        LIVE.replace("Set before running:", "Set:"),
    ]
    for n, text in enumerate(bad):
        assert check(text).returncode != 0, n
    local = LIVE.replace('"$BASE/api/orders"', '"http://localhost:3000/api/orders"')
    assert check(local, "http://localhost:3000").returncode != 0

    plain = tmp_path / "plain.md"
    plain.write_text(LIVE.replace('"$BASE', '"https://uat.acme.test:8443'), encoding="utf-8")
    assert run_script("drafts", "check", plain, env=env).returncode == 0
