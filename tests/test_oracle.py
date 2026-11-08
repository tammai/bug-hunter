import json

from conftest import git, run_script

LOCK = {
    "contracts": "1.1.0",
    "spec": "spec",
    "generated": "2026-11-08T10:00:00Z",
    "criteria": [
        {"id": cid, "feature": cid.split(".")[0], "file": f"features/{cid.split('.')[0]}.md",
         "text_sha256": "0" * 64, "tag": "docs", "priority": "MVP", "level": level,
         "test": None, "departures": []}
        for cid, level in [("F-TSK-01.AC1", 2), ("F-TSK-01.AC2", 2), ("F-TSK-02.AC1", 1),
                           ("F-TSK-03.AC1", 2), ("F-TSK-04.AC1", 0)]
    ],
}


def story(fid, criteria, failure_modes=("none",), extra=""):
    lines = [f"# {fid}", "", "## Story", f"As a member. {extra}", "", "## Acceptance criteria"]
    lines += [f"- [ ] **{cid}** {text} `[docs]`" for cid, text in criteria]
    lines += ["", "## Failure modes", *(f"- {fm}" for fm in failure_modes), ""]
    return "\n".join(lines)


SPEC = {
    "spec/criteria.lock.json": json.dumps(LOCK),
    "spec/domain.md": "# Domain rules\n\n## Roles\nmember creates.\n\n## Identifiers\nTSK-<n>.\n",
    "spec/openapi.json": json.dumps({"paths": {
        "/api/tasks": {"post": {"operationId": "createTask", "x-features": ["F-TSK-01"]},
                       "get": {"operationId": "listTasks", "x-features": ["F-TSK-02"]}}}}),
    "spec/features/F-TSK-01.md": story(
        "F-TSK-01", [("F-TSK-01.AC1", 'Given 2 tasks, when a member creates "A", then TSK-3.'),
                     ("F-TSK-01.AC2", "Given a member, when the title is empty, then 400.")],
        ["Empty title → F-TSK-01.AC2", "Not signed in → F-TSK-01.AC1"],
        "Keys follow domain.md §Identifiers; only domain.md §Roles may create."),
    "spec/features/F-TSK-02.md": story("F-TSK-02", [("F-TSK-02.AC1", "Given tasks, then listed.")]),
    "spec/features/F-TSK-03.md": story("F-TSK-03", [("F-TSK-03.AC1", "Given tasks, then 2.")]),
    "spec/features/F-TSK-04.md": story("F-TSK-04", [("F-TSK-04.AC1", "Given x, then 1.")]),
}

CODE = {
    "src/create.py": "a = 1\nb = 2\nc = 3\n",
    "tests/test_create.py": "x = 1\n",
    **{f"stats/f{i}.py": "a = 1\nb = 2\n" for i in range(1, 9)},
    "stats/f9.py": "a = 1\n",
    ".sdlc/state/2026-01-01-m-create.md": (
        "# create\nChange: docs/sdlc/changes/2026-01-01-m-create.md\n\n## Tasks\n"
        "1. **Create** — AC-001\n   - Files: `./src/create.py`, `tests/test_create.py`\n\n"
        "## Criteria\n- F-TSK-01.AC1 sha256:" + "0" * 64 + "\n"),
    ".sdlc/state/2026-01-03-m-stats.md": (
        "# stats\n\n## Tasks\n1. **Stats** — AC-001\n   - Files: "
        + ", ".join(f"`stats/f{i}.py`" for i in range(1, 10)) + "\n\n"
        "## Criteria\n- F-TSK-03.AC1 sha256:" + "0" * 64 + "\n"),
}

VIEW = {
    "docs/sdlc/changes/2026-01-02-m-view.md": "# view\n\n## Acceptance criteria\n"
                                              "- **AC-001** → F-TSK-02.AC1\n",
    "src/view.py": "".join(f"v{i} = {i}\n" for i in range(5)),
    "tests/test_view.py": "x = 1\n",
}

# Not sdlc records: a `changes` folder outside the docs folder, and a commit naming it.
DECOY = {"src/changes/notes.md": "- **AC-001** → F-TSK-04.AC1\n", "src/other.py": "o = 1\n"}


def commit(repo, files, message):
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message)


def hunted_repo(make_repo):
    repo = make_repo({})
    commit(repo, {**SPEC, **CODE}, "base")
    commit(repo, VIEW, "Add view (docs/sdlc/changes/2026-01-02-m-view.md)")
    commit(repo, DECOY, "Notes (src/changes/notes.md)")
    return repo


def scope(repo, *args):
    result = run_script("oracle", "scope", repo, "--oracle", repo / "spec", *args)
    return result, (json.loads(result.stdout) if result.returncode == 0 else None)


def test_parts_are_features_with_their_spec_and_source_files(make_repo):
    repo = hunted_repo(make_repo)
    result, out = scope(repo)
    assert result.returncode == 0, result.stderr
    parts = {p["feature"]: p for p in out["parts"]}
    create = parts["F-TSK-01"]
    assert create["files"] == ["src/create.py"]
    assert create["story"] == "spec/features/F-TSK-01.md"
    assert [c["id"] for c in create["criteria"]] == ["F-TSK-01.AC1", "F-TSK-01.AC2"]
    assert create["criteria"][0] == {
        "id": "F-TSK-01.AC1", "level": 2,
        "text": 'Given 2 tasks, when a member creates "A", then TSK-3.'}
    assert create["domain_rules"] == ["Roles", "Identifiers"]
    assert create["operations"] == ["createTask"]
    assert (create["changed_lines"], create["failure_modes"]) == (3, 2)
    assert "python-cli" in create["edge_inputs"]

    stats = parts["F-TSK-03"]
    assert stats["files"] == [f"stats/f{i}.py" for i in range(1, 9)]
    assert stats["files_left_out"] == ["stats/f9.py"]
    assert stats["changed_lines"] == 16

    view = parts["F-TSK-02"]
    assert view["files"] == ["src/view.py"]
    assert view["changed_lines"] == 5
    assert view["operations"] == ["listTasks"]

    assert out["not_hunted"] == [{"feature": "F-TSK-04", "reason": (
        "no source files: no sdlc state or commit names its criteria")}]


def test_ranking_puts_unproven_criteria_then_changed_lines_first(make_repo):
    repo = hunted_repo(make_repo)
    _, out = scope(repo)
    assert [p["feature"] for p in out["parts"]] == ["F-TSK-02", "F-TSK-03", "F-TSK-01"]
    assert [p["id"] for p in out["parts"]] == [1, 2, 3]
    assert out["parts"][0]["below_level_2"] is True

    result, out = scope(repo, "--max", "2")
    assert result.returncode == 0, result.stderr
    assert [p["feature"] for p in out["parts"]] == ["F-TSK-02", "F-TSK-03"]
    assert [p["feature"] for p in out["skipped"]] == ["F-TSK-01"]
    assert (out["hunters"], out["est_tokens"]) == (2, 200_000)

    _, out = scope(repo, "--budget", "200000")
    assert [p["feature"] for p in out["parts"]] == ["F-TSK-02"]
    assert out["budget"]["left_out"] == 2
    _, out = scope(repo, "--max", "2", "--budget", "200000")
    assert out["budget"]["left_out"] == 1


def test_a_story_path_outside_the_spec_is_not_read(make_repo):
    repo = hunted_repo(make_repo)
    (repo.parent / "secret.md").write_text("## Failure modes\n- a\n", encoding="utf-8")
    lock = json.loads(SPEC["spec/criteria.lock.json"])
    for c in lock["criteria"]:
        if c["feature"] == "F-TSK-01":
            c["file"] = ".\\features\\F-TSK-01.md"
    (repo / "spec" / "criteria.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    _, out = scope(repo)
    create = next(p for p in out["parts"] if p["feature"] == "F-TSK-01")
    assert create["story"] == "spec/features/F-TSK-01.md"
    assert create["failure_modes"] == 2

    for bad in ("../../secret.md", "", "features/", "features/missing.md"):
        for c in lock["criteria"]:
            if c["feature"] == "F-TSK-01":
                c["file"] = bad
        (repo / "spec" / "criteria.lock.json").write_text(json.dumps(lock), encoding="utf-8")
        _, out = scope(repo)
        create = next(p for p in out["parts"] if p["feature"] == "F-TSK-01")
        assert create["story"] is None, bad
        assert (create["failure_modes"], create["domain_rules"]) == (0, [])


def test_docs_dir_written_with_dot_slash_still_finds_change_files(make_repo):
    repo = hunted_repo(make_repo)
    for docs in ("./docs/sdlc/", "docs//sdlc", "docs/./sdlc"):
        commit(repo, {".sdlc/config.json": json.dumps({"docs_dir": docs})}, f"config {docs}")
        _, out = scope(repo)
        assert "F-TSK-02" in [p["feature"] for p in out["parts"]], docs


def test_a_state_change_path_written_with_backslashes_finds_its_commit(make_repo):
    repo = hunted_repo(make_repo)
    commit(repo, {".sdlc/state/2026-01-05-m-four.md": (
        "# four\nChange: .\\docs\\sdlc\\changes\\2026-01-05-m-four.md\n\n"
        "## Criteria\n- F-TSK-04.AC1 sha256:" + "0" * 64 + "\n")}, "state")
    commit(repo, {"src/four.py": "f = 4\n"}, "Four (docs/sdlc/changes/2026-01-05-m-four.md)")
    _, out = scope(repo)
    four = next(p for p in out["parts"] if p["feature"] == "F-TSK-04")
    assert four["files"] == ["src/four.py"]


def test_the_longest_cited_heading_wins_by_its_normalised_name():
    from oracle import rule_citations

    assert rule_citations("Per domain.md §A B C.", ["A    B", "A B C"]) == (["A B C"], 0)


DRAFT = """# Empty title is accepted
{header}
## What happens
An empty title creates a task.

## Steps to reproduce
```
$ python3 -m app create ""
created TSK-1
```

## Expected
{expected}

## Root cause
`src/create.py`, `create`, line 2: no check.
"""


def check(tmp_path, repo, header, expected):
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT.format(header=header, expected=expected), encoding="utf-8")
    return run_script("drafts", "check", draft, "--oracle", repo / "spec")


def test_expected_cites_the_spec_or_marks_a_spec_gap(make_repo, tmp_path):
    repo = hunted_repo(make_repo)
    (repo / "spec" / "domain.md").write_text(
        "# Domain rules\n\n## Roles\nx\n\n## Roles and permissions\ny\n\n## Straße rules\nz\n\n"
        "## Billing  limits\nw\n", encoding="utf-8")
    good = [("", "400, per F-TSK-01.AC2."), ("", "Only a member may create (domain.md §Roles)."),
            ("", "domain.md §Roles; again domain.md §Roles."),
            ("", "Per domain.md §Roles and permissions."),
            ("", "Per domain.md §Straße rules."), ("", "Per domain.md §Billing  limits."),
            ("", "Per domain.md § Roles."),
            ("Oracle: spec-gap\n", "No criterion or rule covers this.")]
    for header, expected in good:
        result = check(tmp_path, repo, header, expected)
        assert result.returncode == 0, (expected, result.stdout)
    bad = [("", "400, per F-TSK-01.AC9."), ("", "See domain.md §Billing."),
           ("", "See domain.md §Roles-admin."),
           ("", "domain.md §Roles and permissions, and domain.md §Billing."),
           ("", "It should refuse an empty title.")]
    for header, expected in bad:
        result = check(tmp_path, repo, header, expected)
        assert result.returncode == 1, expected
        assert result.stdout.strip() and "Traceback" not in result.stdout + result.stderr


def test_a_bad_oracle_is_one_error_line(make_repo, tmp_path):
    repo = hunted_repo(make_repo)
    for spec in (tmp_path / "no spec", repo / "src"):
        result = run_script("oracle", "scope", repo, "--oracle", spec)
        assert result.returncode == 1 and result.stderr.startswith("error:"), spec
        assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr
    (repo / "spec" / "criteria.lock.json").write_text("{not json", encoding="utf-8")
    result = run_script("oracle", "scope", repo, "--oracle", repo / "spec")
    assert result.returncode == 1 and result.stderr.startswith("error:")
    assert "Traceback" not in result.stderr
