import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import run_script

PAIR = Path(__file__).resolve().parent / "fixtures" / "reference-pair"
KEY_FAIL = {"result": "fail", "step": 1,
            "message": 'step 1 /key: "TSK-0003" does not satisfy rule regex:^TSK-[1-9][0-9]*$'}
PASS = {"result": "pass"}
STEPS = [{"request": {"method": "POST", "path": "/api/tasks", "json": {"title": "C"}},
          "expect": {"status": 201,
                     "json": [{"pointer": "/key", "rule": "regex:^TSK-[1-9][0-9]*$"}]}}]
D1 = {"id": "D-001", "kind": "simplification", "summary": "padded keys", "decided_by": "Tam",
      "match": [{"runner": "http", "pointer": "/key", "rule": "regex:^TSK-\\d{4}$"}]}


def spec_with(tmp_path, registry: str | None) -> Path:
    spec = tmp_path / "spec"
    shutil.copytree(PAIR / "spec", spec)
    if registry is None:
        (spec / "departures.yaml").unlink()
    else:
        (spec / "departures.yaml").write_text(registry, encoding="utf-8")
    return spec


def classify_departure_draft(tmp_path, spec):
    draft = tmp_path / "departure.md"
    shutil.copy(PAIR / "drafts" / "departure.md", draft)
    r1, r2 = tmp_path / "r1.json", tmp_path / "r2.json"
    r1.write_text(json.dumps(KEY_FAIL), encoding="utf-8")
    r2.write_text(json.dumps(PASS), encoding="utf-8")
    return run_script("finding_v1", "classify", "--draft", draft, "--oracle", spec,
                      "--rebuild", r1, "--reference", r2)


ENTRY = ('- id: D-001\n  kind: simplification\n  summary: padded keys\n'
         '  match:\n    - {runner: http, pointer: /key, rule: "regex:^TSK-\\\\d{4}$"}\n')


def test_registry_is_read_and_checked(tmp_path):
    accepted = classify_departure_draft(tmp_path, spec_with(tmp_path / "a", ENTRY
                                                            + '  decided_by: "Tam"\n'))
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout) == {"class": "accepted-departure", "route": "drop",
                                           "departure": "D-001"}
    for registry in (None, ENTRY + "  status: proposed\n"):
        got = classify_departure_draft(tmp_path, spec_with(tmp_path / str(len(str(registry))),
                                                           registry))
        assert got.returncode == 0, got.stderr
        assert json.loads(got.stdout)["class"] == "build-defect", registry
    for n, registry in enumerate((ENTRY, ENTRY.replace("D-001", "D-1") + "  decided_by: T\n",
                                  "- id: [unclosed\n")):
        bad = classify_departure_draft(tmp_path, spec_with(tmp_path / f"bad{n}", registry))
        assert bad.returncode == 1 and bad.stderr.startswith("error:"), registry
        assert "departures.yaml" in bad.stderr and bad.stderr.count("\n") == 1, bad.stderr
    # Never through a link: a spec inside the hunted repo could point one outside it.
    linked = spec_with(tmp_path / "link", None)
    try:
        os.symlink(PAIR / "spec" / "departures.yaml", linked / "departures.yaml")
    except OSError:
        pytest.skip("this OS account can't create symlinks")
    got = classify_departure_draft(tmp_path, linked)
    assert got.returncode == 1 and "departures.yaml" in got.stderr, got.stderr


def test_departure_matches_by_pointer_and_rule():
    from finding_v1 import matching_departure

    other = {**D1, "id": "D-002"}
    assert matching_departure([D1, other], STEPS, KEY_FAIL) == "D-001"
    got_form = {"result": "fail", "step": 1,
                "message": 'step 1 /key: got "TSK-0003", expected "TSK-3"'}
    equals = [{**STEPS[0], "expect": {"status": 201,
                                      "json": [{"pointer": "/key", "equals": "TSK-3"}]}}]
    assert matching_departure([D1], equals, got_form) == "D-001"
    unpadded = {**KEY_FAIL, "message": KEY_FAIL["message"].replace("TSK-0003", "TSK-03")}
    cut = {**KEY_FAIL, "message": 'step 1 /key: "TSK-0003... (sha256 0123456789abcdef)'}
    for result in (unpadded, cut):
        assert matching_departure([D1], STEPS, result) is None, result
    assert matching_departure([{**D1, "status": "proposed", "decided_by": None}], STEPS,
                              KEY_FAIL) is None
    # A check the failure stopped before never ran: it may hide a real defect.
    title = {"pointer": "/title", "equals": "C"}
    later_check = [{**STEPS[0], "expect": {**STEPS[0]["expect"],
                                           "json": [*STEPS[0]["expect"]["json"], title]}}]
    later_step = [*STEPS, {"request": {"method": "GET", "path": "/api/tasks"},
                           "expect": {"status": 200}}]
    # Scoped: criteria first, else features; an entry with neither is unscoped.
    by_criterion = {**D1, "criteria": ["F-TSK-01.AC1"]}
    by_feature = {**D1, "features": ["F-TSK-01"]}
    for entry, criterion, want in ((by_criterion, "F-TSK-01.AC1", "D-001"),
                                   (by_criterion, "F-TSK-01.AC2", None),
                                   (by_criterion, None, None),
                                   (by_feature, "F-TSK-01.AC2", "D-001"),
                                   (by_feature, "F-TSK-02.AC1", None),
                                   (D1, "F-TSK-02.AC1", "D-001")):
        assert matching_departure([entry], STEPS, KEY_FAIL, criterion) == want, (entry, criterion)
    # An earlier check on the same pointer could have written the same message.
    earlier_null = {"result": "fail", "step": 1,
                    "message": 'step 1 /key: got "TSK-0003", expected null'}
    same_pointer = [{**STEPS[0], "expect": {**STEPS[0]["expect"], "json": [
        {"pointer": "/key", "equals": None}, *STEPS[0]["expect"]["json"]]}}]
    for steps, result in ((later_check, KEY_FAIL), (later_step, KEY_FAIL),
                          (STEPS, earlier_null), (same_pointer, KEY_FAIL)):
        assert matching_departure([D1], steps, result) is None, steps


NOT_RUN = {"result": "not run: the proxy refused step 1: request budget used up"}


@pytest.mark.parametrize("reference, covered, defect, want", [
    (NOT_RUN, True, False, ("accepted-departure", "drop", None)),
    # A verified bug-bar defect is never dropped by a departure.
    (PASS, True, True, ("build-defect", "sdlc", None)),
    (KEY_FAIL, True, False, ("spec-gap", "rspec", None)),
])
def test_departure_applies_unless_the_reference_is_the_same_wrong(reference, covered, defect,
                                                                    want):
    from finding_v1 import classify

    got = classify(KEY_FAIL, reference, covered=covered, defect=defect, departure="D-001",
                   alone="build-defect")
    assert (got["class"], got["route"], got.get("propose_departure")) == want
    assert got.get("departure") == ("D-001" if want[0] == "accepted-departure" else None)


def test_departure_flag_is_gone(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    out = tmp_path / "out"
    draft = tmp_path / "departure.md"
    shutil.copy(PAIR / "drafts" / "departure.md", draft)
    r1, r2 = tmp_path / "r1.json", tmp_path / "r2.json"
    r1.write_text(json.dumps(KEY_FAIL), encoding="utf-8")
    r2.write_text(json.dumps(PASS), encoding="utf-8")
    for command in (("write", "--repo", repo, "--out", out), ("classify",)):
        got = run_script("finding_v1", *command, "--draft", draft, "--rebuild", r1,
                         "--reference", r2, "--departure", "D-001")
        assert got.returncode != 0 and "--departure" in got.stderr, command
    assert not out.exists()
