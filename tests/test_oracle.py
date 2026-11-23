import hashlib
import json
import os
import subprocess

import pytest
from conftest import git, run_script

TEXTS = {
    "F-TSK-01.AC1": 'Given 2 tasks, when a member creates "A", then TSK-3.',
    "F-TSK-01.AC2": "Given a member, when the title is empty, then 400.",
    "F-TSK-02.AC1": "Given tasks, then listed.",
    "F-TSK-03.AC1": "Given tasks, then 2.",
    "F-TSK-04.AC1": "Given x, then 1.",
}


def sha(text):
    """A criterion's `text_sha256` as the lock holds it: its line after the ID, tag included."""
    return hashlib.sha256(f"{text} `[docs]`".encode()).hexdigest()


LOCK = {
    "contracts": "1.1.0",
    "spec": "spec",
    "generated": "2026-11-08T10:00:00Z",
    "criteria": [
        {"id": cid, "feature": cid.split(".")[0], "file": f"features/{cid.split('.')[0]}.md",
         "text_sha256": sha(TEXTS[cid]), "tag": "docs", "priority": "MVP", "level": level,
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
        "F-TSK-01", [(c, TEXTS[c]) for c in ("F-TSK-01.AC1", "F-TSK-01.AC2")],
        ["Empty title → F-TSK-01.AC2", "Not signed in → F-TSK-01.AC1"],
        "Keys follow domain.md §Identifiers; only domain.md §Roles may create."),
    **{f"spec/features/{f}.md": story(f, [(f"{f}.AC1", TEXTS[f"{f}.AC1"])])
       for f in ("F-TSK-02", "F-TSK-03", "F-TSK-04")},
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


def test_live_keeps_only_parts_serving_http(make_repo):
    repo = hunted_repo(make_repo)
    result, _ = scope(repo, "--live")
    assert result.returncode == 1 and result.stderr.startswith("error:"), result.stdout
    assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr
    commit(repo, {"src/create.py": '@app.post("/api/tasks")\ndef create():\n    pass\n'},
           "Route")
    result, out = scope(repo, "--live")
    assert result.returncode == 0, result.stderr
    assert [(p["id"], p["feature"]) for p in out["parts"]] == [(1, "F-TSK-01")]
    assert "live-http" in out["parts"][0]["edge_inputs"]
    assert out["hunters"] == 1
    assert {"feature": "F-TSK-02", "reason": "its files define no HTTP routes"} \
        in out["not_hunted"]
    # A route file ranked past the 8 kept files still counts.
    grown = {f"stats/f{i}.py": "".join(f"v{n} = {n}\n" for n in range(10)) for i in range(1, 9)}
    commit(repo, {**grown, "stats/f9.py": '@app.get("/api/stats")\n'}, "Stats route")
    result, out = scope(repo, "--live")
    stats = next(p for p in out["parts"] if p["feature"] == "F-TSK-03")
    # The hunter gets the route file: it takes the place of the lowest-ranked kept file.
    assert "stats/f9.py" in stats["files"] and len(stats["files"]) == 8, stats
    assert stats["files_left_out"] == ["stats/f8.py"], stats
    # Its lines are counted for the files the hunter gets: f1-f7 at 14 each, f9 at 3.
    assert stats["changed_lines"] == 7 * 14 + 3, stats


def test_no_source_files_is_one_error_line(make_repo):
    repo = make_repo({})
    commit(repo, SPEC, "spec only")
    for args in ((), ("--live",)):
        result, _ = scope(repo, *args)
        assert result.returncode == 1 and result.stderr.startswith("error:"), (args, result.stdout)
        assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr


def test_spec_files_are_not_read_through_symlinks(make_repo, monkeypatch):
    import os

    import oracle

    repo = hunted_repo(make_repo)
    linked = {"F-TSK-01.md", "domain.md", "openapi.json"}
    # This Windows account can't make symlinks, so the OS's answer is stood in for.
    real = os.path.islink
    monkeypatch.setattr(oracle.os.path, "islink",
                        lambda p: os.path.basename(str(p)) in linked or real(p))
    out = oracle.build(str(repo), repo / "spec")
    create = next(p for p in out["parts"] if p["feature"] == "F-TSK-01")
    assert create["story"] is None
    assert (create["domain_rules"], create["operations"], create["failure_modes"]) == ([], [], 0)

    linked.clear()
    linked.add("features")  # a folder between the spec root and the story
    create = next(p for p in oracle.build(str(repo), repo / "spec")["parts"]
                  if p["feature"] == "F-TSK-01")
    assert create["story"] is None

    linked.add("criteria.lock.json")
    with pytest.raises(oracle.BadOracle):
        oracle.build(str(repo), repo / "spec")

    linked.clear()
    linked.add("spec")  # the spec folder itself, inside the hunted repo
    for spelled in (repo / "spec", repo / ".." / repo.name / "spec"):
        with pytest.raises(oracle.BadOracle):
            oracle.build(str(repo), spelled)

    # A Windows junction is a link too.
    linked.clear()
    monkeypatch.setattr(oracle.os.path, "isjunction",
                        lambda p: os.path.basename(str(p)) == "features")
    create = next(p for p in oracle.build(str(repo), repo / "spec")["parts"]
                  if p["feature"] == "F-TSK-01")
    assert create["story"] is None


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


def test_rule_citations_read_a_backticked_file_name_and_a_comma():
    from oracle import rule_citations

    for text in ("Per `domain.md` §Roles.", "Per domain.md, §Roles.", "Per `domain.md`, § Roles."):
        assert rule_citations(text, ["Roles"]) == (["Roles"], 0), text


@pytest.mark.parametrize("line", ["**Oracle: spec-gap**", "`Oracle: spec-gap`",
                                  "**Oracle:** spec-gap", "Oracle: `spec-gap`"])
def test_a_bold_or_backticked_spec_gap_line_counts(line):
    from oracle import is_spec_gap

    assert is_spec_gap(f"# Title\n{line}\n\n## What happens\nx\n")
    assert not is_spec_gap(f"# Title\n{line.replace('spec-gap', 'spec-gaps')}\n")


def test_standalone_criterion_ids_are_criteria(make_repo):
    import oracle

    assert oracle.CRITERION.findall("Per AC-001 and F-TSK-01.AC2, not XAC-002 or AC-01.") == \
        ["AC-001", "F-TSK-01.AC2"]
    lock = {"criteria": [{"id": "AC-001", "feature": "F-ONE", "file": "features/one.md",
                          "text_sha256": sha("Given x, then 1."), "priority": "MVP",
                          "level": 2}]}
    repo = make_repo({})
    commit(repo, {
        "spec/criteria.lock.json": json.dumps(lock),
        "spec/features/one.md": story("F-ONE", [("AC-001", "Given x, then 1.")]),
        "src/one.py": "o = 1\n",
        ".sdlc/state/2026-01-01-l-one.md": (
            "# one\n\n## Tasks\n1. **One** — AC-001\n   - Files: `src/one.py`\n\n"
            "## Criteria\n- AC-001 sha256:" + sha("Given x, then 1.") + "\n"),
    }, "one")
    result, out = scope(repo)
    assert result.returncode == 0, result.stderr
    [one] = out["parts"]
    assert one["files"] == ["src/one.py"]
    assert one["criteria"] == [{"id": "AC-001", "level": 2, "text": "Given x, then 1."}]


def test_struck_through_criteria_are_not_read(make_repo):
    repo = hunted_repo(make_repo)
    text = story("F-TSK-01", [(c, TEXTS[c]) for c in ("F-TSK-01.AC1", "F-TSK-01.AC2")],
                 extra="Only domain.md §Roles may create.")
    text = text.replace("\n\n## Failure modes", (
        "\n- [ ] ~~**F-TSK-01.AC1** Old keys per domain.md §Identifiers. `[docs]`~~ replaced"
        "\n\n## Failure modes"))
    commit(repo, {"spec/features/F-TSK-01.md": text}, "strike")
    _, out = scope(repo)
    create = next(p for p in out["parts"] if p["feature"] == "F-TSK-01")
    assert create["criteria"][0] == {"id": "F-TSK-01.AC1", "level": 2,
                                     "text": TEXTS["F-TSK-01.AC1"]}
    assert create["domain_rules"] == ["Roles"]


def test_an_edited_criterion_drops_to_level_0(make_repo):
    repo = hunted_repo(make_repo)
    commit(repo, {"spec/features/F-TSK-03.md": story(
        "F-TSK-03", [("F-TSK-03.AC1", "Given tasks, then 3.")])}, "edit")
    _, out = scope(repo)
    stats = next(p for p in out["parts"] if p["feature"] == "F-TSK-03")
    assert stats["criteria"][0]["level"] == 0 and stats["below_level_2"] is True
    assert [p["feature"] for p in out["parts"]] == ["F-TSK-03", "F-TSK-02", "F-TSK-01"]


def files_of(repo, feature):
    _, out = scope(repo)
    return next((p["files"] for p in out["parts"] if p["feature"] == feature), None)


def test_a_commit_that_only_mentions_a_change_file_isnt_its_commit(make_repo):
    repo = hunted_repo(make_repo)
    view_change = "docs/sdlc/changes/2026-01-02-m-view.md"
    commit(repo, {"src/mention.py": "m = 1\n"}, f"Tidy, as planned in {view_change}")
    assert files_of(repo, "F-TSK-02") == ["src/view.py"]
    commit(repo, {"src/view2.py": "w = 1\n"}, f"More view\n\nRecord: {view_change}\n")
    assert files_of(repo, "F-TSK-02") == ["src/view.py", "src/view2.py"]


def test_a_change_file_links_criteria_only_in_its_acceptance_criteria(make_repo):
    repo = hunted_repo(make_repo)
    other = "docs/sdlc/changes/2026-01-07-m-other.md"
    commit(repo, {other: "# other\n\n## Failure modes\n- Empty → F-TSK-04.AC1\n",
                  "src/other_x.py": "x = 1\n"}, f"Other ({other})")
    assert files_of(repo, "F-TSK-04") is None


def test_a_merge_commit_naming_a_change_lists_its_files(make_repo):
    repo = hunted_repo(make_repo)
    merged = "docs/sdlc/changes/2026-01-06-m-merged.md"
    commit(repo, {merged: "# merged\n\n## Acceptance criteria\n- **AC-001** → F-TSK-04.AC1\n"},
           "Record")
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, {"src/merged.py": "m = 2\n"}, "wip")
    git(repo, "checkout", "-q", "-")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-ff", "side",
        "-m", f"Merge side ({merged})")
    assert files_of(repo, "F-TSK-04") == ["src/merged.py"]


@pytest.mark.skipif(os.name == "nt", reason="a Windows file name can't hold a quote")
def test_paths_git_would_quote_still_match(make_repo):
    repo = hunted_repo(make_repo)
    four = "docs/sdlc/changes/2026-01-08-m-four.md"
    commit(repo, {four: "# four\n\n## Acceptance criteria\n- **AC-001** → F-TSK-04.AC1\n",
                  'src/say "hi".py': "a = 1\nb = 2\n"}, f"Four ({four})")
    commit(repo, {'stats/q "1".py': "a = 1\nb = 2\nc = 3\n",
                  ".sdlc/state/2026-01-03-m-stats.md": (
                      '# stats\n\n## Tasks\n1. **Stats** — AC-001\n   - Files: `stats/q "1".py`'
                      "\n\n## Criteria\n- F-TSK-03.AC1\n")}, "quoted")
    _, out = scope(repo)
    parts = {p["feature"]: p for p in out["parts"]}
    assert (parts["F-TSK-04"]["files"], parts["F-TSK-04"]["changed_lines"]) == \
        (['src/say "hi".py'], 2)
    assert (parts["F-TSK-03"]["files"], parts["F-TSK-03"]["changed_lines"]) == \
        (['stats/q "1".py'], 3)


def test_headings_inside_code_fences_are_text(make_repo):
    import oracle

    assert oracle._section("## Criteria\n```\n## Tasks\n```\n- a\n", "Criteria") == \
        ["```", "## Tasks", "```", "- a"]
    repo = hunted_repo(make_repo)
    (repo / "spec" / "domain.md").write_text(
        "# Domain rules\n\n## Roles\n```\n## Fake\n```\n\n## Identifiers\nx\n", encoding="utf-8")
    assert oracle.domain_headings(repo / "spec") == ["Roles", "Identifiers"]


def test_install_warnings_are_printed_in_oracle_mode(make_repo):
    repo = hunted_repo(make_repo)
    commit(repo, {"we$ird/package-lock.json": "{}\n"}, "lockfile")
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=repo, input=b"",
                          capture_output=True).stdout.decode().strip()
    # Through stdin: a Windows command line can't carry non-UTF-8 bytes.
    subprocess.run(["git", "update-index", "--index-info"],
                   input=f"100644 {blob}\t".encode() + b"bad\xff.py\n",
                   cwd=repo, check=True, capture_output=True)
    result, _ = scope(repo)
    assert result.returncode == 0, result.stderr
    assert "aren't UTF-8" in result.stderr and "unsafe folder name" in result.stderr
    assert "Traceback" not in result.stderr


def test_git_runs_a_fixed_number_of_times(make_repo, monkeypatch):
    import oracle

    repo = hunted_repo(make_repo)
    calls = []
    real = oracle._git
    monkeypatch.setattr(oracle, "_git", lambda *a, **k: calls.append(a) or real(*a, **k))
    oracle.build(str(repo), repo / "spec")
    first = len(calls)
    assert first <= 3, calls
    for n in range(5, 9):
        change = f"docs/sdlc/changes/2026-02-0{n}-m-x{n}.md"
        commit(repo, {change: f"# x\n\n## Acceptance criteria\n- **AC-001** → F-TSK-0{n}.AC1\n",
                      f"src/x{n}.py": "x = 1\n"}, f"X ({change})")
    lock = json.loads(SPEC["spec/criteria.lock.json"])
    lock["criteria"] += [{**lock["criteria"][-1], "id": f"F-TSK-0{n}.AC1",
                          "feature": f"F-TSK-0{n}"} for n in range(5, 9)]
    (repo / "spec" / "criteria.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    calls.clear()
    out = oracle.build(str(repo), repo / "spec")
    assert len(out["parts"]) == 7 and len(calls) == first, calls


def test_integrations_are_read_only_for_kept_parts(make_repo, monkeypatch, capsys):
    import oracle

    repo = hunted_repo(make_repo)
    seen = []
    monkeypatch.setattr(oracle.scope, "_calls_third_parties",
                        lambda root, files: seen.append(list(files)) or False)
    assert oracle._main(["scope", str(repo), "--oracle", str(repo / "spec"), "--max", "1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert seen == [out["parts"][0]["files"]]


def test_deeply_nested_spec_json_is_one_error_line_or_ignored(make_repo):
    deep = "[" * 100000 + "]" * 100000
    repo = hunted_repo(make_repo)
    (repo / "spec" / "openapi.json").write_text(deep, encoding="utf-8")
    (repo / ".sdlc").mkdir(exist_ok=True)
    (repo / ".sdlc" / "config.json").write_text(deep, encoding="utf-8")
    result, parts = scope(repo)
    assert result.returncode == 0 and "Traceback" not in result.stderr, result.stderr
    (repo / "spec" / "criteria.lock.json").write_text(deep, encoding="utf-8")
    result, _ = scope(repo)
    assert result.returncode == 1 and result.stderr.startswith("error:"), result.stderr
    assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr


def test_git_reads_the_same_history_whatever_the_owners_git_setup(make_repo, tmp_path,
                                                                  monkeypatch):
    import oracle

    repo = hunted_repo(make_repo)
    args = ("log", "-z", "--numstat", "--no-renames", "--format=%x01%H")
    clean = oracle._git(str(repo), *args)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    git(elsewhere, "init", "-q")
    monkeypatch.setenv("GIT_DIR", str(elsewhere / ".git"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "log.showRoot")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "diff.algorithm")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "patience")
    assert oracle._git(str(repo), *args) == clean


def test_a_named_merge_and_its_named_branch_commits_count_once(make_repo):
    repo = hunted_repo(make_repo)
    merged = "docs/sdlc/changes/2026-01-06-m-merged.md"
    commit(repo, {merged: "# merged\n\n## Acceptance criteria\n- **AC-001** → F-TSK-04.AC1\n"},
           "Record")
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, {"src/merged.py": "a = 1\nb = 2\nc = 3\n"}, f"Build ({merged})")
    git(repo, "checkout", "-q", "-")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-ff", "side",
        "-m", f"Merge side ({merged})")
    _, out = scope(repo)
    part = next(p for p in out["parts"] if p["feature"] == "F-TSK-04")
    assert part["files"] == ["src/merged.py"] and part["changed_lines"] == 3, part


def test_commit_messages_are_not_read_when_no_record_names_a_change(make_repo, monkeypatch):
    import oracle

    repo = make_repo({})
    plain = {k: v for k, v in {**SPEC, **CODE}.items()
             if not k.startswith((".sdlc/", "docs/sdlc/"))}
    commit(repo, plain, "base")
    calls = []
    real = oracle._git
    monkeypatch.setattr(oracle, "_git", lambda *a, **k: calls.append(a) or real(*a, **k))
    out = oracle.build(str(repo), repo / "spec")
    assert len(out["not_hunted"]) == 4, out
    assert not any("--format=%H%x00%P%x00%B" in a for a in calls), calls
