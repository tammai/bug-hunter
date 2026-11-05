import json

from conftest import run_script

FILES = {
    "src/cli.py": "",
    "src/my dir/naïve.py": "",
    "b10/x.py": "",
    "b2/y.py": "",
    "README.md": "",
    "uv.lock": "",
    "tests/test_cli.py": "",
    "src/test_foo.py": "",
    "pkg/a_test.go": "",
    "web/app.test.ts": "",
    **{f"big/f{i}.py": "" for i in range(1, 8)},
}


def scope(repo, *args):
    result = run_script("scope", repo, *args)
    return result, (json.loads(result.stdout) if result.returncode == 0 else None)


def test_splits_tracked_source_files_into_parts(make_repo):
    repo = make_repo(FILES)
    result, out = scope(repo)
    assert result.returncode == 0, result.stderr
    assert [(p["dir"], p["files"]) for p in out["parts"]] == [
        ("b2", ["b2/y.py"]),
        ("b10", ["b10/x.py"]),
        ("big", [f"big/f{i}.py" for i in range(1, 6)]),
        ("big", ["big/f6.py", "big/f7.py"]),
        ("src", ["src/cli.py"]),
        ("src/my dir", ["src/my dir/naïve.py"]),
    ]
    assert [p["id"] for p in out["parts"]] == [1, 2, 3, 4, 5, 6]
    assert out["hunters"] == 6
    assert out["est_tokens"] == 600_000
    assert out["skipped"] == []


def test_max_caps_hunters_and_cost(make_repo):
    repo = make_repo(FILES)
    result, out = scope(repo, "--max", "2")
    assert result.returncode == 0, result.stderr
    assert [p["dir"] for p in out["parts"]] == ["b2", "b10"]
    assert [p["dir"] for p in out["skipped"]] == ["big", "big", "src", "src/my dir"]
    assert out["hunters"] == 2
    assert out["est_tokens"] == 200_000

    for bad in ("0", "-1"):
        result = run_script("scope", repo, "--max", bad)
        assert result.returncode == 2
        assert "--max" in result.stderr
        assert "Traceback" not in result.stderr


def test_paths_restrict_and_errors_are_clean(make_repo, tmp_path):
    repo = make_repo(FILES)
    result, out = scope(repo, "src", "b2/y.py")
    assert result.returncode == 0, result.stderr
    files = [f for p in out["parts"] for f in p["files"]]
    assert files == ["b2/y.py", "src/cli.py", "src/my dir/naïve.py"]

    result = run_script("scope", repo, "nope")
    assert result.returncode == 1
    assert "nope" in result.stderr
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1

    not_git = tmp_path / "plain dir"
    not_git.mkdir()
    result = run_script("scope", not_git)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1
