import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import run_script

PAIR = Path(__file__).resolve().parent / "fixtures" / "reference-pair"
KEY_FAIL = {"result": "fail", "step": 1,
            "message": 'step 1 /key: "TSK-0003" does not satisfy rule regex:^TSK-[1-9][0-9]*$',
            "check": {"pointer": "/key", "value": "TSK-0003"}}
PASS = {"result": "pass"}
STEPS = [{"request": {"method": "POST", "path": "/api/tasks", "json": {"title": "C"}},
          "expect": {"status": 201,
                     "json": [{"pointer": "/key", "rule": "regex:^TSK-[1-9][0-9]*$"}]}}]
HTTP = {"runner": "http", "steps": STEPS}
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


def results_for(tmp_path, rebuild=KEY_FAIL):
    r1, r2 = tmp_path / "r1.json", tmp_path / "r2.json"
    r1.write_text(json.dumps(rebuild), encoding="utf-8")
    r2.write_text(json.dumps(PASS), encoding="utf-8")
    return r1, r2


def classify_departure_draft(tmp_path, spec, rebuild=KEY_FAIL):
    draft = tmp_path / "departure.md"
    shutil.copy(PAIR / "drafts" / "departure.md", draft)
    r1, r2 = results_for(tmp_path, rebuild)
    return run_script("finding_v1", "classify", "--draft", draft, "--oracle", spec,
                      "--rebuild", r1, "--reference", r2)


def write_departure_draft(make_repo, tmp_path, spec):
    repo = make_repo({"a.py": ""})
    draft = tmp_path / "departure.md"
    shutil.copy(PAIR / "drafts" / "departure.md", draft)
    r1, r2 = results_for(tmp_path)
    out = tmp_path / "out"
    return out, run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft,
                           "--oracle", spec, "--rebuild", r1, "--reference", r2)


ENTRY = ('- id: D-001\n  kind: simplification\n  summary: padded keys\n'
         '  match:\n    - {runner: http, pointer: /key, rule: "regex:^TSK-\\\\d{4}$"}\n')
DECIDED = ENTRY + '  decided_by: "Tam"\n'


def test_an_accepted_entry_is_matched(tmp_path):
    got = classify_departure_draft(tmp_path, spec_with(tmp_path, DECIDED))
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout) == {"class": "accepted-departure", "route": "drop",
                                      "departure": "D-001"}


def test_no_registry_matches_nothing(tmp_path):
    got = classify_departure_draft(tmp_path, spec_with(tmp_path, None))
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout)["class"] == "build-defect"


@pytest.mark.parametrize("registry", [
    ENTRY,  # no decided_by
    ENTRY.replace("D-001", "D-1") + "  decided_by: T\n",
    "- id: [unclosed\n",
])
def test_an_invalid_registry_is_refused(tmp_path, registry):
    bad = classify_departure_draft(tmp_path, spec_with(tmp_path, registry))
    assert bad.returncode == 1 and bad.stderr.startswith("error:"), registry
    assert "departures.yaml" in bad.stderr and bad.stderr.count("\n") == 1, bad.stderr


def test_a_linked_registry_is_refused(tmp_path):
    # Never through a link: a spec inside the hunted repo could point one outside it.
    linked = spec_with(tmp_path, None)
    try:
        os.symlink(PAIR / "spec" / "departures.yaml", linked / "departures.yaml")
    except OSError:
        pytest.skip("this OS account can't create symlinks")
    got = classify_departure_draft(tmp_path, linked)
    assert got.returncode == 1 and "departures.yaml" in got.stderr, got.stderr


def test_a_proposed_entry_is_warned_about(make_repo, tmp_path):
    spec = spec_with(tmp_path / "s", ENTRY + "  status: proposed\n")
    got = classify_departure_draft(tmp_path, spec)
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout)["class"] == "build-defect"
    out, wrote = write_departure_draft(make_repo, tmp_path, spec)
    assert wrote.returncode == 0, wrote.stderr
    assert json.loads(Path(wrote.stdout.strip()).read_text(encoding="utf-8"))["class"] \
        == "build-defect"
    for stderr in (got.stderr, wrote.stderr):
        lines = stderr.splitlines()
        assert len(lines) == 1 and lines[0].startswith("warning: departures.yaml: D-001 is "
                                                       "proposed"), stderr


def test_a_departure_id_over_nine_digits_is_refused(make_repo, tmp_path):
    long_id = "D-0000000001"
    spec = spec_with(tmp_path / "s", DECIDED.replace("D-001", long_id))
    got = classify_departure_draft(tmp_path, spec)
    out, wrote = write_departure_draft(make_repo, tmp_path, spec)
    for result in (got, wrote):
        assert result.returncode == 1 and result.stderr.startswith("error:"), result.stderr
        assert result.stderr.count("\n") == 1 and "departures.yaml" in result.stderr
        assert long_id not in result.stderr
    assert not out.exists()
    nine = classify_departure_draft(tmp_path, spec_with(tmp_path / "n",
                                                        DECIDED.replace("D-001", "D-000000001")))
    assert nine.returncode == 0 and json.loads(nine.stdout)["departure"] == "D-000000001"


@pytest.mark.parametrize("registry", [
    ENTRY.replace("D-001", "D-0000000001"),  # no decided_by: contracts would name the ID
    DECIDED.replace("D-001", "D-0000000001") + DECIDED.replace("D-001", "D-0000000001"),
    DECIDED.replace("D-001", '"D-001\\n"'),
    DECIDED.replace("D-001", '"D-0٠1"'),
])
def test_a_bad_departure_id_is_refused_without_echoing_it(tmp_path, registry):
    got = classify_departure_draft(tmp_path, spec_with(tmp_path, registry))
    assert got.returncode == 1 and got.stderr.startswith("error:"), got.stderr
    assert got.stderr.count("\n") == 1 and "departures.yaml" in got.stderr, got.stderr
    assert "0000000001" not in got.stderr and "٠" not in got.stderr, got.stderr


def test_departures_command_checks_the_registry_before_the_run(tmp_path):
    def check(registry):
        return run_script("finding_v1", "departures", "--oracle",
                          spec_with(tmp_path / str(abs(hash(str(registry)))), registry))
    for registry in (None, DECIDED):
        got = check(registry)
        assert got.returncode == 0 and got.stderr == "", (registry, got.stderr)
    proposed = check(ENTRY + "  status: proposed\n")
    assert proposed.returncode == 0, proposed.stderr
    assert proposed.stderr.startswith("warning: departures.yaml: D-001 is proposed")
    assert proposed.stderr.count("\n") == 1, proposed.stderr
    for registry in (DECIDED.replace("D-001", "D-0000000001"), ENTRY, "- id: [unclosed\n"):
        bad = check(registry)
        assert bad.returncode == 1 and bad.stderr.startswith("error:"), registry
        assert bad.stderr.count("\n") == 1 and "departures.yaml" in bad.stderr, bad.stderr


def test_a_check_matches_only_a_value_that_fails_the_last_check():
    from finding_v1 import matching_departure

    loose = {**D1, "match": [{"runner": "http", "pointer": "/key", "rule": "regex:^TSK-"}]}
    passing = {**KEY_FAIL, "check": {"pointer": "/key", "value": "TSK-3"}}
    assert matching_departure([loose], HTTP, passing) is None
    assert matching_departure([loose], HTTP, KEY_FAIL) == "D-001"
    equals = {"runner": "http", "steps": [{**STEPS[0], "expect": {
        "status": 201, "json": [{"pointer": "/key", "equals": "TSK-0003"}]}}]}
    assert matching_departure([D1], equals, KEY_FAIL) is None
    capture_only = {"runner": "http", "steps": [{**STEPS[0], "expect": {
        "status": 201, "json": [{"pointer": "/key", "capture": "k"}]}}]}
    same_as = {"runner": "http", "steps": [{**STEPS[0], "expect": {
        "status": 201, "json": [{"pointer": "/key", "rule": "same-as:k"}]}}]}
    for repro in (capture_only, same_as):
        assert matching_departure([D1], repro, KEY_FAIL) is None, repro


def test_deeply_nested_json_is_one_error_line(tmp_path):
    spec = spec_with(tmp_path / "s", DECIDED)
    nested = "[" * 100000 + "]" * 100000
    draft = tmp_path / "departure.md"
    shutil.copy(PAIR / "drafts" / "departure.md", draft)
    r1, r2 = results_for(tmp_path)
    r1.write_text(nested, encoding="utf-8")
    got = run_script("finding_v1", "classify", "--draft", draft, "--oracle", spec,
                     "--rebuild", r1, "--reference", r2)
    deep = tmp_path / "deep.md"
    head, rest = draft.read_text(encoding="utf-8").split("## Observed (finding-v1)\n", 1)
    deep.write_text(f"{head}## Observed (finding-v1)\n```json\n{nested}\n```\n\n"
                    + rest.split("```\n", 1)[1], encoding="utf-8")
    rendered = run_script("finding_v1", "render", "--draft", deep)
    for result in (got, rendered):
        assert result.returncode == 1 and result.stderr.startswith("error:"), result.stderr
        assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr


def test_registry_with_an_equivalence_trace_is_read_and_never_matches(tmp_path):
    # product-rebuild's equiv.py writes this entry when a person accepts a red equivalence trace.
    trace = ('- id: D-002\n  kind: deliberate-change\n  summary: accepted trace\n'
             '  match:\n    - {runner: http, rule: "equiv-trace:invoices-total"}\n'
             '  decided_by: "Tam"\n')
    got = classify_departure_draft(tmp_path, spec_with(tmp_path / "s", trace + DECIDED))
    assert got.returncode == 0, got.stderr
    assert json.loads(got.stdout)["departure"] == "D-001"


def test_departure_matches_on_the_structured_check():
    from finding_v1 import matching_departure

    other = {**D1, "id": "D-002"}
    assert matching_departure([D1, other], HTTP, KEY_FAIL) == "D-001"
    # Decided from `check` alone: the message's wording is never read.
    reworded = {**KEY_FAIL, "message": "the key came back padded"}
    assert matching_departure([D1], HTTP, reworded) == "D-001"
    no_check = {k: v for k, v in KEY_FAIL.items() if k != "check"}
    assert matching_departure([D1], HTTP, no_check) is None
    equals = {"runner": "http", "steps": [{**STEPS[0], "expect": {
        "status": 201, "json": [{"pointer": "/key", "equals": "TSK-3"}]}}]}
    assert matching_departure([D1], equals, KEY_FAIL) == "D-001"
    unpadded = {**KEY_FAIL, "check": {"pointer": "/key", "value": "TSK-03"}}
    assert matching_departure([D1], HTTP, unpadded) is None
    assert matching_departure([{**D1, "status": "proposed", "decided_by": None}], HTTP,
                              KEY_FAIL) is None
    # Scoped: criteria first, else features; an entry with neither is unscoped.
    by_criterion = {**D1, "criteria": ["F-TSK-01.AC1"]}
    by_feature = {**D1, "features": ["F-TSK-01"]}
    for entry, criterion, want in ((by_criterion, "F-TSK-01.AC1", "D-001"),
                                   (by_criterion, "F-TSK-01.AC2", None),
                                   (by_criterion, None, None),
                                   (by_feature, "F-TSK-01.AC2", "D-001"),
                                   (by_feature, "F-TSK-02.AC1", None),
                                   (D1, "F-TSK-02.AC1", "D-001")):
        assert matching_departure([entry], HTTP, KEY_FAIL, criterion) == want, (entry, criterion)


def test_a_check_is_bound_to_the_last_check_and_checked(tmp_path):
    from finding_v1 import matching_departure

    # A check the failure stopped before never ran: it may hide a real defect.
    title = {"pointer": "/title", "equals": "C"}
    later_check = [{**STEPS[0], "expect": {**STEPS[0]["expect"],
                                           "json": [*STEPS[0]["expect"]["json"], title]}}]
    later_step = [*STEPS, {"request": {"method": "GET", "path": "/api/tasks"},
                           "expect": {"status": 200}}]
    # An earlier check on the same pointer could have failed instead.
    same_pointer = [{**STEPS[0], "expect": {**STEPS[0]["expect"], "json": [
        {"pointer": "/key", "equals": None}, *STEPS[0]["expect"]["json"]]}}]
    other_pointer = {**KEY_FAIL, "check": {"pointer": "/title", "value": "TSK-0003"}}
    for steps, result in ((later_check, KEY_FAIL), (later_step, KEY_FAIL),
                          (same_pointer, KEY_FAIL), (STEPS, other_pointer)):
        assert matching_departure([D1], {"runner": "http", "steps": steps}, result) is None, \
            (steps, result)
    spec = spec_with(tmp_path / "s", DECIDED)
    got = classify_departure_draft(tmp_path, spec)
    assert got.returncode == 0 and json.loads(got.stdout)["departure"] == "D-001", got.stderr
    old = {k: v for k, v in KEY_FAIL.items() if k != "check"}
    got = classify_departure_draft(tmp_path, spec, old)
    assert got.returncode == 0 and json.loads(got.stdout)["class"] == "build-defect", got.stderr
    for check in ("x", None, {"pointer": 1, "value": 2}, {"pointer": "/key"},
                  {"pointer": "/key", "value": 1, "extra": 1}):
        bad = classify_departure_draft(tmp_path, spec, {**KEY_FAIL, "check": check})
        assert bad.returncode == 1 and bad.stderr.startswith("error:"), check
        assert bad.stderr.count("\n") == 1, bad.stderr


def test_departure_needs_an_http_runner():
    from finding_v1 import matching_departure

    assert matching_departure([D1], HTTP, KEY_FAIL) == "D-001"
    for runner in ("cli", "playwright", None):
        assert matching_departure([D1], {"runner": runner, "steps": STEPS}, KEY_FAIL) is None


def test_departure_flag_is_gone(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    out = tmp_path / "out"
    draft = tmp_path / "departure.md"
    shutil.copy(PAIR / "drafts" / "departure.md", draft)
    r1, r2 = results_for(tmp_path)
    for command in (("write", "--repo", repo, "--out", out), ("classify",)):
        got = run_script("finding_v1", *command, "--draft", draft, "--rebuild", r1,
                         "--reference", r2, "--departure", "D-001")
        assert got.returncode != 0 and "--departure" in got.stderr, command
    assert not out.exists()
