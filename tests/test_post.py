import json

from conftest import run_script
from test_drafts import GOOD


def make_drafts(tmp_path, count=3):
    drafts = tmp_path / "drafts ü"
    drafts.mkdir()
    for n in range(1, count + 1):
        text = GOOD.replace("# Sort puts B10 before B2", f"# Bug {n}: $(touch pwned) `x`")
        (drafts / f"{n:02d}.md").write_text(text, encoding="utf-8")
    return drafts


def creates(calls):
    return [c for c in calls() if c[:2] == ["issue", "create"]]


def test_files_named_drafts_once(tmp_path, fake_gh):
    env, calls = fake_gh
    drafts = make_drafts(tmp_path)

    result = run_script("post", drafts, "1", "03", "--label", "bug", env=env, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert creates(calls) == [
        ["issue", "create", "--title", f"Bug {n}: $(touch pwned) `x`",
         "--body-file", str(drafts / f"{n:02d}.md"), "--label", "bug"]
        for n in (1, 3)
    ]
    assert not (tmp_path / "pwned").exists()
    assert "https://github.com/o/r/issues/1" in result.stdout
    posted = json.loads((drafts / "posted.json").read_text(encoding="utf-8"))
    assert posted == {"01": "https://github.com/o/r/issues/1", "03": "https://github.com/o/r/issues/2"}

    result = run_script("post", drafts, "01", "2", "--label", "bug", env=env, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "01" in result.stdout and "already filed" in result.stdout
    assert [c[3] for c in creates(calls)] == [
        "Bug 1: $(touch pwned) `x`", "Bug 3: $(touch pwned) `x`", "Bug 2: $(touch pwned) `x`"
    ]
    posted = json.loads((drafts / "posted.json").read_text(encoding="utf-8"))
    assert sorted(posted) == ["01", "02", "03"]


def test_refuses_before_filing_and_keeps_partial_progress(tmp_path, fake_gh):
    env, calls = fake_gh
    drafts = make_drafts(tmp_path)

    missing = run_script("post", drafts, "1", "07", "--label", "bug", env=env)
    assert missing.returncode == 1 and "07" in missing.stderr
    assert creates(calls) == []

    (drafts / "02.md").write_text("# Bad draft\n\n## What happens\nx\n", encoding="utf-8")
    bad = run_script("post", drafts, "1", "2", "--label", "bug", env=env)
    assert bad.returncode == 1 and "02" in bad.stderr and "Expected" in bad.stderr
    assert creates(calls) == []

    not_a_number = run_script("post", drafts, "../01", "--label", "bug", env=env)
    assert not_a_number.returncode == 1 and creates(calls) == []

    env["FAKE_GH_AUTH_EXIT"] = "1"
    logged_out = run_script("post", drafts, "1", "--label", "bug", env=env)
    assert logged_out.returncode == 1 and "gh auth login" in logged_out.stderr
    assert creates(calls) == []
    del env["FAKE_GH_AUTH_EXIT"]

    (drafts / "posted.json").write_text("{broken", encoding="utf-8")
    corrupt = run_script("post", drafts, "1", "--label", "bug", env=env)
    assert corrupt.returncode == 1 and "posted.json" in corrupt.stderr
    assert creates(calls) == []
    (drafts / "posted.json").unlink()

    (drafts / "02.md").write_text(GOOD, encoding="utf-8")
    env["FAKE_GH_FAIL_AT"] = "2"
    partial = run_script("post", drafts, "1", "2", "3", "--label", "bug", env=env)
    assert partial.returncode == 1
    assert "02" in partial.stderr and "could not create issue" in partial.stderr
    assert len(creates(calls)) == 2
    posted = json.loads((drafts / "posted.json").read_text(encoding="utf-8"))
    assert posted == {"01": "https://github.com/o/r/issues/1"}

    no_gh = {**env, "PATH": str(tmp_path / "empty")}
    gone = run_script("post", drafts, "3", "--label", "bug", env=no_gh)
    assert gone.returncode == 1 and "Traceback" not in gone.stderr
