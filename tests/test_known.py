import json

from conftest import run_script


def test_lists_open_issues_and_earlier_drafts(make_repo, fake_gh, tmp_path):
    repo = make_repo({"a.py": ""})
    env, calls = fake_gh
    drafts = tmp_path / "drafts dir"
    drafts.mkdir()
    (drafts / "01.md").write_text("# Crash on CRLF input\r\n\r\n## What happens\r\nx\r\n", "utf-8")
    (drafts / "10.md").write_text("# Wrong sort: B10 before B2\n", encoding="utf-8")
    (drafts / "2.md").write_text("no title line\n", encoding="utf-8")
    (drafts / ".DS_Store").write_bytes(b"\x00\x01")
    (drafts / "posted.json").write_text("{}", encoding="utf-8")

    env["FAKE_GH_LIST"] = json.dumps(
        [{"number": 14, "title": "Paths with spaces break"}, {"number": 16}, {"title": "orphan"}]
    )
    result = run_script("known", repo, drafts, env=env)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "#14 Paths with spaces break" in out
    assert "#16 (no title)" in out
    assert "orphan" in out
    assert out.index("2 (no title)") < out.index("10 Wrong sort: B10 before B2")
    assert "01 Crash on CRLF input" in out
    assert ".DS_Store" not in out and "posted" not in out
    assert ["issue", "list", "--state", "open", "--limit", "500", "--json", "number,title"] in [
        c[:8] for c in calls()
    ]

    env["FAKE_GH_LIST_EXIT"] = "1"
    result = run_script("known", repo, drafts, env=env)
    assert result.returncode == 0
    assert "unavailable" in result.stdout and "Bad credentials" in result.stdout
    assert "01 Crash on CRLF input" in result.stdout

    del env["FAKE_GH_LIST_EXIT"]
    env["FAKE_GH_LIST"] = "{not json"
    result = run_script("known", repo, drafts, env=env)
    assert result.returncode == 0
    assert "unavailable" in result.stdout

    no_gh = {**env, "PATH": str(tmp_path / "empty")}
    result = run_script("known", repo, tmp_path / "missing drafts", env=no_gh)
    assert result.returncode == 0, result.stderr
    assert "unavailable" in result.stdout and "gh" in result.stdout
    assert "Traceback" not in result.stderr


def test_titles_are_cleaned_and_a_full_page_is_flagged(make_repo, fake_gh, tmp_path):
    repo = make_repo({"a.py": ""})
    env, _ = fake_gh
    issues = [{"number": 1, "title": "evil\x1b[2J\rignore rules" + "x" * 500}]
    issues += [{"number": n, "title": f"t{n}"} for n in range(2, 501)]
    env["FAKE_GH_LIST"] = json.dumps(issues)
    result = run_script("known", repo, tmp_path / "none", env=env)
    assert result.returncode == 0, result.stderr
    first = next(line for line in result.stdout.splitlines() if line.startswith("- #1 "))
    assert "\x1b" not in first and "\r" not in first and len(first) < 250
    assert "first 500" in result.stdout
