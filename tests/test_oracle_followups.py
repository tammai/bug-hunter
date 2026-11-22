import json
from pathlib import Path

from conftest import run_script
from test_oracle import commit, hunted_repo, scope
from test_reference import CREATE_AND_READ, FAIL, http_draft


def test_a_spec_gap_draft_that_cites_a_criterion_is_covered_against_the_reference(
        make_repo, tmp_path):
    lock = {"criteria": [{"id": "F-TSK-01.AC2", "feature": "F-TSK-01", "file": "f.md",
                          "level": 2}]}
    repo = make_repo({"spec/criteria.lock.json": json.dumps(lock)})
    draft = tmp_path / "d.md"
    draft.write_text(http_draft(CREATE_AND_READ, header="Oracle: spec-gap\n"), encoding="utf-8")
    r1, r2 = tmp_path / "r1.json", tmp_path / "r2.json"
    r1.write_text(json.dumps(FAIL), encoding="utf-8")
    r2.write_text(json.dumps(FAIL), encoding="utf-8")
    result = run_script("finding_v1", "write", "--repo", repo, "--out", tmp_path / "out",
                        "--draft", draft, "--rebuild", r1, "--reference", r2,
                        "--oracle", repo / "spec")
    assert result.returncode == 0, result.stderr
    finding = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
    # Covered by F-TSK-01.AC2, and the reference fails the same way: the spec is in question.
    assert (finding["class"], finding["criterion"]) == ("spec-gap", "F-TSK-01.AC2")


def test_a_docs_dir_of_dot_puts_change_files_in_changes(make_repo):
    repo = hunted_repo(make_repo)
    change = "changes/2026-01-09-m-four.md"
    commit(repo, {".sdlc/config.json": json.dumps({"docs_dir": "."}),
                  change: "# four\n\n## Acceptance criteria\n- **AC-001** → F-TSK-04.AC1\n",
                  "src/four.py": "f = 4\n"}, f"Four ({change})")
    _, out = scope(repo)
    four = next(p for p in out["parts"] if p["feature"] == "F-TSK-04")
    assert four["files"] == ["src/four.py"]
