import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import SCRIPTS, run_script
from drafts import problems
from test_live_proxy import (
    ORIGIN,
    call,
    call_no_redirect_with,
    entries,
    home_env,
    raw,
    start_stub,
    stop,
    write_targets,
)

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts" / "v1" / "contracts.py"
PAIR = Path(__file__).resolve().parent / "fixtures" / "reference-pair"
TOKEN_A = "Bearer Rb7Qx2LmVn58"
TOKEN_B = "Bearer Rf3Kw9PzJd14"
REFUSED = "X-Bug-Hunter-Refused"


def free_base() -> str:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{probe.getsockname()[1]}"


def start_pair(repo, target, reference, env, log, *extra):
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPTS / "live_proxy.py"), "--repo", str(repo), "--target", target,
         "--reference", reference, "--log", str(log), *extra],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    first, second = proc.stdout.readline().strip(), proc.stdout.readline().strip()
    assert first.startswith("listening on http://127.0.0.1:"), (first, proc.stderr.read())
    assert second.startswith("reference listening on http://127.0.0.1:"), second
    return proc, first.removeprefix("listening on "), second.removeprefix(
        "reference listening on ")


def test_each_listener_reaches_only_its_own_target(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    a_base, b_base = free_base(), free_base()
    a_net, b_net = a_base.removeprefix("http://"), b_base.removeprefix("http://")
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    stub_a, a_base, a_log = start_stub(tmp_path / "a", [
        {"path": "/who", "responses": [{"body": {"app": "rebuild"}}]},
        {"path": "/echo", "responses": [{"body": f"{TOKEN_A} {TOKEN_B} {b_base}/x {b_net}"}]},
    ], int(a_net.split(":")[1]))
    stub_b, b_base, b_log = start_stub(tmp_path / "b", [
        {"path": "/who", "responses": [{"body": {"app": "reference"}}]},
        {"path": "/echo", "responses": [{"body": f"{TOKEN_B} {TOKEN_A} {a_base}/x {a_net}"}]},
    ], int(b_net.split(":")[1]))
    write_targets(targets, {
        "uat": {"url": a_base, "accounts": {"alice": {"Authorization": TOKEN_A}}},
        "ref": {"url": b_base, "accounts": {"bob": {"Authorization": TOKEN_B}}}})
    log = tmp_path / "proxy.jsonl"
    proxy, base, ref_base = start_pair(repo, "uat", "ref", env, log)
    try:
        assert json.loads(call(base + "/who")[2]) == {"app": "rebuild"}
        assert json.loads(call(ref_base + "/who")[2]) == {"app": "reference"}
        for listener, other in ((base, b_net), (ref_base, a_net)):
            assert b" 400 " in raw(listener, f"GET http://{other}/who HTTP/1.1\r\nHost: {other}"
                                             "\r\n\r\n".encode())
            assert b" 400 " in raw(listener, b"GET /../who HTTP/1.1\r\nHost: x\r\n\r\n")
        spoofed = {"Host": b_net, "X-Forwarded-Host": b_net}
        assert json.loads(call(base + "/who", headers=spoofed)[2]) == {"app": "rebuild"}
        spoofed = {"Host": a_net, "X-Forwarded-Host": a_net}
        assert json.loads(call(ref_base + "/who", headers=spoofed)[2]) == {"app": "reference"}
        routed = {"X-Original-URL": "/who", "X-Rewrite-URL": "/who", "X-Forwarded-Prefix": "/b",
                  "Forwarded": f"host={b_net}", "X-Host": b_net, "X-Original-Host": b_net,
                  "X-HTTP-Host-Override": b_net, "X-Forwarded-Uri": "/who"}
        assert json.loads(call(base + "/who", headers=routed)[2]) == {"app": "rebuild"}
        assert call(base + "/who", headers={"X-Bug-Hunter-Account": "bob"})[0] == 400
        assert call(ref_base + "/who", headers={"X-Bug-Hunter-Account": "alice"})[0] == 400
        bodies = [call_no_redirect_with(base + "/echo", {"X-Bug-Hunter-Account": "alice"})[2],
                  call_no_redirect_with(ref_base + "/echo", {"X-Bug-Hunter-Account": "bob"})[2]]
    finally:
        stop(proxy, stub_a, stub_b)
    for body in bodies:
        for secret in ("Rb7Qx2LmVn58", "Rf3Kw9PzJd14", a_net, b_net):
            assert secret not in body, (secret, body)
    assert [e["path"] for e in entries(a_log)] == ["/who", "/who", "/who", "/echo"]
    assert [e["path"] for e in entries(b_log)] == ["/who", "/who", "/echo"]
    sent = {k.lower() for k in entries(a_log)[2]["headers"]}
    assert not sent & {"x-original-url", "x-rewrite-url", "x-forwarded-prefix", "forwarded",
                       "x-host", "x-original-host", "x-http-host-override", "x-forwarded-uri"}
    assert {e.get("target") for e in entries(log)} == {"rebuild", "reference"}


def test_one_masker_covers_both_targets():
    from live_proxy import _masker

    nested = {"url": "https://uat.acme.test", "accounts": {"a": {
        "Authorization": "Basic YWxpY2U6V2ludGVyMjAyNA=="}}}  # alice:Winter2024
    longer = {"url": "https://uat.acme.test:9443", "accounts": {"a": {
        "Authorization": "Basic YWxpY2U6V2ludGVyMjAyNCF4N1E="}}}  # alice:Winter2024!x7Q
    mask = _masker(nested, "http://127.0.0.1:1", ((longer, "http://127.0.0.1:2"),))
    out = mask(b"pw=Winter2024!x7Q at https://uat.acme.test:9443/x and https://uat.acme.test/y")
    assert out == b"pw=<redacted> at http://127.0.0.1:2/x and http://127.0.0.1:1/y", out
    single = _masker({"url": "http://uat-server", "accounts": {}}, "http://127.0.0.1:1")
    assert b"uat-server" not in single(b"see http://uat-server:8443/x")
    wide = _masker({"url": "http://bücher.test:8080", "accounts": {}}, "http://127.0.0.1:1")
    assert wide("at http://bücher.test:8080/x".encode()) == b"at http://127.0.0.1:1/x"


def test_writes_per_target_and_one_shared_budget(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    rules = [{"path": "/orders", "responses": [{"status": 201, "body": {"id": 7}}]},
             {"path": "/fake", "responses": [{"headers": {REFUSED: "1"}, "body": "ok"}]}]
    stub_a, a_base, a_log = start_stub(tmp_path / "a", rules)
    stub_b, b_base, b_log = start_stub(tmp_path / "b", rules)
    write_targets(targets, {"uat": {"url": a_base, "writes": True},
                            "ref": {"url": b_base, "writes": False}})
    log = tmp_path / "p.jsonl"
    proxy, base, ref_base = start_pair(repo, "uat", "ref", env, log, "--max-requests", "3")
    try:
        assert call(base + "/orders", "POST", b"{}", {"Content-Type": "application/json"}
                    )[0] == 201
        status, headers, _ = call(ref_base + "/orders", "POST", b"{}",
                                  {"Content-Type": "application/json"})
        assert status == 403 and headers.get(REFUSED) == "1"
        status, headers, _ = call(base + "/fake")
        assert status == 200 and REFUSED not in headers
        assert call(ref_base + "/orders")[0] == 201
        for listener in (base, ref_base):
            status, headers, _ = call(listener + "/orders")
            assert status == 429 and headers.get(REFUSED) == "1"
        status, headers, _ = call(base + "/" + "a" * 70000)
        assert status == 414 and headers.get(REFUSED) == "1"
    finally:
        stop(proxy, stub_a, stub_b)
    assert [e["method"] for e in entries(a_log)] == ["POST", "GET"]
    assert [e["method"] for e in entries(b_log)] == ["GET"]
    assert any(e["status"] == 414 and e.get("target") == "rebuild" for e in entries(log))


def test_reference_flags_are_checked(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    write_targets(targets, {"uat": {"url": "https://uat.example.test"},
                            "same": {"url": "https://uat.example.test/"},
                            "v1": {"url": "https://uat.example.test/v1"},
                            "ref": {"url": "https://ref.example.test", "writes": False,
                                    "accounts": {"bob": {"Authorization": TOKEN_B}}}})
    log = tmp_path / "l.jsonl"
    for target, reference in (("uat", "uat"), ("uat", "same"), ("uat", "v1"), ("uat", "nope"),
                              ("http://localhost:3999", "http://127.0.0.1:3999")):
        # --check: a pair that is wrongly accepted exits 0 instead of serving forever.
        result = run_script("live_proxy", "--repo", repo, "--target", target, "--reference",
                            reference, "--log", log, "--check", env=env)
        assert result.returncode == 1, reference
        assert result.stderr.startswith("error:") and "Traceback" not in result.stderr
        if reference == "v1":
            assert "origin" in result.stderr, result.stderr
        assert result.stderr.count("\n") == 1, result.stderr
    result = run_script("live_proxy", "--repo", repo, "--target", "uat", "--reference", "ref",
                        "--log", log, "--check", env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "target ok: uat (writes: no; accounts: none)",
        "reference ok: ref (writes: no; accounts: bob)",
        "warning: account bob is on the reference only; its steps can't run on both targets"]


def http_draft(steps, observed=None, header=""):
    observed = observed if observed is not None else {
        "rebuild": {"result": "fail", "step": 1, "message": "step 1: status 500, expected 400"},
        "reference": {"result": "pass"}}
    text = (f"# Orders crash\nSet before running: `BASE`, `REF_BASE`, `ACCEPT_ACCOUNT_BOB`\n"
            f"Severity: high\n{header}\n## What happens\nIt crashes.\n\n"
            "## Steps to reproduce\nRendered from the Repro section.\n\n"
            f"## Repro (finding-v1)\n```json\n{json.dumps(steps)}\n```\n\n")
    if observed != "omit":
        text += f"## Observed (finding-v1)\n```json\n{json.dumps(observed)}\n```\n\n"
    return text + ("## Expected\nF-TSK-01.AC2: 400.\n\n"
                   "## Root cause\n`app.py`, `create`, line 3: no check.\n")


CREATE_AND_READ = [
    {"request": {"method": "POST", "path": "/items", "account": "BOB", "json": {"name": "x"}},
     "expect": {"status": 201, "json": [{"pointer": "/id", "rule": "int", "capture": "item"}]}},
    {"request": {"method": "GET", "path": "/items/{item}"},
     "expect": {"status": 200, "json": [{"pointer": "/name", "equals": "x"}]}},
]


def replay(tmp_path, text, base, env=None, name="d.md"):
    draft = tmp_path / name
    draft.write_text(text, encoding="utf-8")
    return run_script("finding_v1", "replay", "--draft", draft, "--base", base, env=env)


def test_replay_reports_pass_fail_and_not_run(make_repo, tmp_path):
    import os

    stub, stub_base, stub_log = start_stub(tmp_path, [
        {"path": "/items", "method": "POST", "responses": [{"status": 201, "body": {"id": 7}}]},
        {"path": "/items/7", "responses": [{"body": {"name": "x"}}]},
        {"path": "/odd", "responses": [{"body": {"name": "\u009b31m"}}]},
        {"path": "/said", "responses": [{"body": {"name": "db: request failed: timeout"}}]},
        {"path": "/long1", "responses": [{"body": {"name": "x" * 600 + "1"}}]},
        {"path": "/long2", "responses": [{"body": {"name": "x" * 600 + "2"}}]},
    ])
    stub_redirects = [
        {"path": "/go", "responses": [{"status": 302, "headers": {"Location": "/items/7"}}]},
        {"path": "/away", "responses": [{"status": 302, "headers": {
            "Location": "http://example.invalid/x"}}]}]
    # An outside proxy in the environment must never carry a replay's requests.
    env = {**os.environ, "ACCEPT_ACCOUNT_BOB": "Authorization: Bearer Zz9Yy8Xx7Ww6",
           "HTTP_PROXY": free_base(), "http_proxy": free_base(), "NO_PROXY": ""}
    (tmp_path / "r").mkdir()
    redirector, redirect_base, _ = start_stub(tmp_path / "r", stub_redirects + [
        {"path": "/items/7", "responses": [{"body": {"name": "x"}}]}])
    try:
        passed = replay(tmp_path, http_draft(CREATE_AND_READ), stub_base, env)
        followed = replay(tmp_path, http_draft([
            {"request": {"method": "GET", "path": "/go"},
             "expect": {"status": 200, "json": [{"pointer": "/name", "equals": "x"}]}},
            {"request": {"method": "GET", "path": "/away"}, "expect": {"status": 302}}]),
            redirect_base, env)
        odd = replay(tmp_path, http_draft([{"request": {"method": "GET", "path": "/odd"},
                                            "expect": {"status": 200, "json": [
                                                {"pointer": "/name", "equals": "y"}]}}]),
                     stub_base, env)

        def name_is_y(path):
            return http_draft([{"request": {"method": "GET", "path": path}, "expect": {
                "status": 200, "json": [{"pointer": "/name", "equals": "y"}]}}])
        said = replay(tmp_path, name_is_y("/said"), stub_base, env)
        long1 = replay(tmp_path, name_is_y("/long1"), stub_base, env)
        long2 = replay(tmp_path, name_is_y("/long2"), stub_base, env)
        wrong = [CREATE_AND_READ[0], {**CREATE_AND_READ[1], "expect": {
            "status": 200, "json": [{"pointer": "/name", "equals": "y"}]}}]
        failed = replay(tmp_path, http_draft(wrong), stub_base, env)
        unset = replay(tmp_path, http_draft(CREATE_AND_READ), stub_base)
        repo = make_repo({"a.py": ""}, origin=ORIGIN)
        home, targets = home_env(tmp_path)
        write_targets(targets, {"ro": {"url": stub_base}})
        proxy = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "live_proxy.py"), "--repo", str(repo), "--target",
             "ro", "--log", str(tmp_path / "p.jsonl")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=home)
        proxy_base = proxy.stdout.readline().strip().removeprefix("listening on ")
        refused = replay(tmp_path, http_draft(CREATE_AND_READ), proxy_base, env)
        stop(proxy)
    finally:
        stop(stub, redirector)
    assert passed.returncode == 0 and json.loads(passed.stdout) == {"result": "pass"}
    assert json.loads(followed.stdout) == {"result": "pass"}, followed.stdout
    assert odd.stdout.isascii() and "\\u009b" in odd.stdout
    assert json.loads(said.stdout)["result"] == "fail", said.stdout
    cut = [json.loads(r.stdout)["message"] for r in (long1, long2)]
    assert cut[0] != cut[1] and all(len(m) <= 500 for m in cut), cut
    assert json.loads(failed.stdout) == {
        "result": "fail", "step": 2, "message": 'step 2 /name: got "x", expected "y"'}
    auth = {k.lower(): v for k, v in entries(stub_log)[0]["headers"].items()}
    assert "authorization" in auth
    assert json.loads(unset.stdout)["result"].startswith("not run: ACCEPT_ACCOUNT_BOB")
    assert json.loads(refused.stdout)["result"].startswith("not run: the proxy refused")
    gone = replay(tmp_path, http_draft(CREATE_AND_READ), free_base(), env)
    assert json.loads(gone.stdout)["result"].startswith("not run: ")
    bad = replay(tmp_path, http_draft([{"request": {"method": "GET", "path": "items"},
                                        "expect": {"status": 200}}]), stub_base, env)
    assert bad.returncode == 1 and bad.stderr.startswith("error:")
    assert bad.stderr.count("\n") == 1 and "Traceback" not in bad.stderr


def test_http_repro_renders_both_results(tmp_path):
    draft = tmp_path / "d.md"
    draft.write_text(http_draft(CREATE_AND_READ), encoding="utf-8")
    result = run_script("finding_v1", "render", "--draft", draft)
    assert result.returncode == 0, result.stderr
    text = draft.read_text(encoding="utf-8")
    steps = text.split("## Steps to reproduce", 1)[1].split("\n## ", 1)[0]
    assert 'step 1: POST /items as BOB {"name": "x"}' in steps
    assert '$ python3 finding_v1.py replay --draft <this draft> --base "$BASE"' in steps
    assert '"message": "step 1: status 500, expected 400"' in steps
    assert '--base "$REF_BASE"' in steps and '{"result": "pass"}' in steps
    assert problems(text) == []
    odd = {"rebuild": {"result": "fail", "step": 1, "message": "step 1 /n: got \u009b31m"},
           "reference": {"result": "pass"}}
    draft.write_text(http_draft(CREATE_AND_READ, odd), encoding="utf-8")
    assert run_script("finding_v1", "render", "--draft", draft).returncode == 0
    assert "\u009b" not in draft.read_text(encoding="utf-8").split("## Steps to reproduce")[1]
    for observed in ("omit", {"rebuild": {"result": "maybe"}, "reference": {"result": "pass"}},
                     {"rebuild": {"result": "pass"}}):
        draft.write_text(http_draft(CREATE_AND_READ, observed), encoding="utf-8")
        result = run_script("finding_v1", "render", "--draft", draft)
        assert result.returncode == 1 and result.stderr.startswith("error:"), observed
        assert result.stderr.count("\n") == 1, result.stderr


FAIL = {"result": "fail", "step": 1, "message": "step 1: status 500, expected 400"}
OTHER = {"result": "fail", "step": 1, "message": "step 1: status 201, expected 400"}
PASS = {"result": "pass"}
NOT_RUN = {"result": "not run: the proxy refused step 1: request budget used up"}


@pytest.mark.parametrize("rebuild, reference, covered, defect, departure, alone, want", [
    (FAIL, PASS, True, False, None, "build-defect", ("build-defect", "sdlc", None)),
    (FAIL, PASS, False, False, None, "spec-gap", ("build-defect", "sdlc", None)),
    (FAIL, FAIL, True, True, None, "build-defect",
     ("build-defect", "sdlc", "reference-defect-not-copied")),
    (FAIL, FAIL, False, True, None, "spec-gap", ("reference-defect", "human", None)),
    (FAIL, PASS, True, False, "D-001", "build-defect", ("accepted-departure", "drop", None)),
    (FAIL, OTHER, True, False, "D-001", "build-defect", ("accepted-departure", "drop", None)),
    (FAIL, FAIL, True, False, None, "build-defect", ("spec-gap", "rspec", None)),
    (FAIL, OTHER, False, False, None, "build-defect", ("build-defect", "sdlc", None)),
    (FAIL, NOT_RUN, False, True, None, "spec-gap", ("spec-gap", "rspec", None)),
    (FAIL, NOT_RUN, True, False, None, "build-defect", ("build-defect", "sdlc", None)),
    (FAIL, FAIL, True, True, "D-001", "build-defect",
     ("build-defect", "sdlc", "reference-defect-not-copied")),
    # A verified draft whose fresh replay passes: the runs disagree, never dropped.
    (PASS, PASS, True, False, None, "build-defect", ("flaky", "orchestrator", None)),
    (PASS, FAIL, True, True, None, "build-defect", ("flaky", "orchestrator", None)),
    # Not a finding: the rebuild matches a reference nothing faults.
    (FAIL, FAIL, False, False, None, "build-defect", None),
    # The rebuild didn't run: the run's environment, for the orchestrator, never a drop.
    (NOT_RUN, PASS, True, False, None, "build-defect", ("environment", "orchestrator", None)),
])
def test_classification_table_every_row(rebuild, reference, covered, defect, departure, alone,
                                        want):
    from finding_v1 import BadDraft, classify

    if want is None:
        with pytest.raises(BadDraft):
            classify(rebuild, reference, covered=covered, defect=defect, departure=departure,
                     alone=alone)
        return
    got = classify(rebuild, reference, covered=covered, defect=defect, departure=departure,
                   alone=alone)
    assert (got["class"], got["route"], got.get("propose_departure")) == want
    if departure and got["class"] == "accepted-departure":
        assert got["departure"] == departure


def routed(path):
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, str(CONTRACTS), "finding", str(path)],
                            capture_output=True, text=True, encoding="utf-8", env=env)
    return result.returncode, result.stdout.strip()


def test_write_takes_class_from_both_results(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    out = tmp_path / "out"
    draft = tmp_path / "d.md"
    draft.write_text(http_draft(CREATE_AND_READ), encoding="utf-8")
    r1, r2 = tmp_path / "r1.json", tmp_path / "r2.json"
    r1.write_text(json.dumps(FAIL), encoding="utf-8")
    r2.write_text(json.dumps(PASS), encoding="utf-8")
    result = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft,
                        "--rebuild", r1, "--reference", r2)
    assert result.returncode == 0, result.stderr
    finding = json.loads((out / "BH-0001.json").read_text(encoding="utf-8"))
    assert finding["repro"] == {"runner": "http", "steps": CREATE_AND_READ,
                                "env": ["ACCEPT_BASE_URL", "ACCEPT_ACCOUNT_BOB"]}
    assert finding["observed"] == {"rebuild": FAIL["message"], "reference": "as expected"}
    assert (finding["class"], finding["route"]) == ("build-defect", "sdlc")
    assert routed(out / "BH-0001.json")[0] == 0
    # The finding's draft shows the results it was classified from, not the hunter's.
    r1.write_text(json.dumps(OTHER), encoding="utf-8")
    result = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft,
                        "--rebuild", r1, "--reference", r2)
    assert result.returncode == 0, result.stderr
    second = json.loads((out / "BH-0002.json").read_text(encoding="utf-8"))
    assert OTHER["message"] in second["draft"] and FAIL["message"] not in second["draft"]
    assert second["class"] == "build-defect"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    r1.write_text(json.dumps(FAIL), encoding="utf-8")
    r2.write_text(json.dumps(FAIL), encoding="utf-8")
    for extra, names in ((("--rebuild", tmp_path / "missing.json", "--reference", r2),
                          "--rebuild"),
                         (("--rebuild", bad, "--reference", r2), "--rebuild"),
                         (("--rebuild", r1, "--reference", r2), "not a finding")):
        result = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft",
                            draft, *extra)
        assert result.returncode == 1 and result.stderr.startswith("error:"), extra
        assert names in result.stderr, result.stderr
        assert result.stderr.count("\n") == 1 and "Traceback" not in result.stderr
    assert sorted(p.name for p in out.iterdir()) == ["BH-0001.json", "BH-0002.json"]


def test_write_refuses_target_hosts_and_logins(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    write_targets(targets, {
        "uat": {"url": "https://uat.example.test", "accounts": {
            "alice": {"Authorization": TOKEN_A}}},
        "ref": {"url": "https://ref.example.test", "accounts": {
            "bob": {"Authorization": TOKEN_B},
            "carol": {"Authorization": "Basic Y2Fyb2w6UzNjcmV0IXBhc3MveA=="}}},  # S3cret!pass/x
        # A plain service name, which the draft's own words ($REF_BASE, "reference") contain.
        "short": {"url": "http://ref:4000"}})
    out = tmp_path / "out"
    draft = tmp_path / "d.md"
    draft.write_text(http_draft(CREATE_AND_READ), encoding="utf-8")
    reference = tmp_path / "ref.json"
    reference.write_text(json.dumps(PASS), encoding="utf-8")
    found = {}
    for name, ref_target, message in (
            ("host", "ref", 'step 1 /next: got "https://ref.example.test/x"'),
            ("login", "ref", 'step 1 /who: got "Rf3Kw9PzJd14"'),
            ("encoded", "ref", 'step 1 /next: got "/login?p=S3cret%21pass%2Fx"'),
            ("short host", "short", 'step 1 /next: got "http://ref:4000/x"'),
            ("clean", "ref", "step 1: status 500, expected 400"),
            ("clean short", "short", "step 1: status 500, expected 400")):
        rebuild = tmp_path / f"{name}.json"
        rebuild.write_text(json.dumps({**FAIL, "message": message}), encoding="utf-8")
        found[name] = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft",
                                 draft, "--rebuild", rebuild, "--reference", reference,
                                 "--target", "uat", "--ref-target", ref_target, env=env)
    for name, words in (("host", "reference's host"), ("login", "account bob"),
                        ("encoded", "account carol"), ("short host", "reference's host")):
        result = found[name]
        assert result.returncode == 1 and result.stderr.startswith("error:"), name
        assert words in result.stderr and "masking" in result.stderr, result.stderr
        assert "Rf3Kw9PzJd14" not in result.stderr and "S3cret" not in result.stderr
        assert result.stderr.count("\n") == 1
    for name in ("clean", "clean short"):
        assert found[name].returncode == 0, (name, found[name].stderr)
    assert sorted(p.name for p in out.iterdir()) == ["BH-0001.json", "BH-0002.json"]
    # A leak in the hunter's own text is the draft's, not the masking's.
    hunter_text = http_draft(CREATE_AND_READ).replace("It crashes.", "ref.example.test crashes.")
    draft.write_text(hunter_text, encoding="utf-8")
    result = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft,
                        "--rebuild", tmp_path / "clean.json", "--reference", reference,
                        "--target", "uat", "--ref-target", "ref", env=env)
    assert result.returncode == 1 and "draft" in result.stderr, result.stderr
    assert "masking" not in result.stderr
    # A cli draft's observed text is the hunter's own What happens, never a target's echo.
    cli = tmp_path / "cli.md"
    cli.write_text("# Crash\nSeverity: high\n\n## What happens\nref.example.test crashes.\n\n"
                   "## Steps to reproduce\nRendered from the Repro section.\n\n"
                   '## Repro (finding-v1)\n```json\n[{"command": "true", "stdout": ""}]\n```\n\n'
                   "## Expected\nNo crash.\n\n## Root cause\n`a.py`, `f`, line 1: x.\n",
                   encoding="utf-8")
    result = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", cli,
                        "--target", "uat", "--ref-target", "ref", env=env)
    assert result.returncode == 1 and "draft" in result.stderr, result.stderr
    assert "masking" not in result.stderr


def _encodings(text):
    """The spellings a target or a JSON/HTML/URL layer may give the same text."""
    from urllib.parse import quote

    once = quote(text, safe="")
    # As json.dumps writes a target's string into a fail message: a newline or tab right
    # before the host, slashes escaped, and the whole thing JSON-encoded again (and again).
    json_once = text.replace("/", "\\/").replace(" ", "\\n")
    json_twice = json.dumps(json_once)[1:-1]
    return {"raw": text, "json": text.replace("/", "\\/"), "unicode": text.replace("/", "\\u002F"),
            "percent": once, "percent twice": quote(once, safe=""),
            "entity": text.replace("/", "&#x2F;"), "upper": text.upper(),
            "newline": text.replace(" ", "\\n"), "tab": text.replace(" ", "\\t"),
            "json twice": json_twice, "json three times": json.dumps(json_twice)[1:-1],
            "hex": text.replace("/", "\\x2F").replace(" ", "\\x20"),
            "ansi": text.replace(" ", "\x1b[31m"), "ansi escaped": text.replace(" ", "\\u001b[31m"),
            "underscore": text.replace(" ", "_"), "cjk": text.replace(" ", "连接")}


TARGETS = {
    # target URL: (a leaking text, texts that must not count as the target)
    "https://ref.example.test": (["see https://ref.example.test/x", "at sso.ref.example.test",
                                  "at ref.example.test"],
                                 ["ref.example.org is another site"]),
    # Known limit: a protocol-relative //uat with no scheme is not counted.
    "http://uat": (["curl http://uat/x", "https://bob@uat/x"],
                   ["a uat-like name, the /api/uat path, $REF_BASE and the reference",
                    "the @uat.get('/x') decorator, qa@uat.com and //uat.example.org",
                    "Cannot GET //uat/users, and $BASE//uat/x"]),
    "http://ref:4000": (["got http://ref:4000/x", "at ref:4000"],
                        ["$REF_BASE, the reference, ref:40001"]),
    "http://127.0.0.1:5000": (["got http://127.0.0.1:5000/x", "got http://localhost:5000/x",
                               "got http://[::1]:5000/x", "at 127.0.0.1:5000"],
                              ["the proxy at http://127.0.0.1:50003/x"]),
    "https://10.0.0.1": (["at https://10.0.0.1/x", "at 10.0.0.1"], ["at 10.0.0.12"]),
    "https://[2001:db8::1]:8443": (["at https://[2001:db8::1]:8443/x", "at 2001:db8::1"],
                                   ["at fe80:2001:db8::12"]),
}


@pytest.mark.parametrize("url", TARGETS)
def test_leak_scan_catches_every_host_form(url):
    from drafts import leaks

    target = {"url": url, "accounts": {}}
    leaking, clean = TARGETS[url]
    for text in leaking:
        for name, spelled in _encodings(text).items():
            assert leaks(spelled, target, "REF_BASE", replay=True), (url, name, spelled)
    for text in clean:
        assert not leaks(text, target, "REF_BASE", replay=True), (url, text)
    # Logins are checked on the same decoded spellings.
    account = {"url": url, "accounts": {"carol": {
        "Authorization": "Basic Y2Fyb2w6UzNjcmV0IXBhc3MveA=="}}}  # carol:S3cret!pass/x
    assert leaks("next=%2Flogin%3Fp%3DS3cret%2521pass%252Fx", account, "REF_BASE", replay=True)


def test_draft_check_hides_the_reference_too(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    write_targets(targets, {
        "uat": {"url": "https://uat.example.test", "accounts": {
            "alice": {"Authorization": TOKEN_A}}},
        "ref": {"url": "https://ref.example.test", "accounts": {
            "bob": {"Authorization": TOKEN_B}}}})
    good = http_draft(CREATE_AND_READ)
    cases = {"good": good,
             "host": good.replace("It crashes.", "It crashes on ref.example.test."),
             "token": good.replace("It crashes.", "It crashes for Rf3Kw9PzJd14."),
             "setup": good.replace(", `REF_BASE`", "")}
    found = {}
    for name, text in cases.items():
        draft = tmp_path / f"{name}.md"
        draft.write_text(text, encoding="utf-8")
        assert run_script("finding_v1", "render", "--draft", draft).returncode == 0
        result = run_script("drafts", "check", draft, "--repo", repo, "--target", "uat",
                            "--reference", "ref", env=env)
        found[name] = (result.returncode, result.stdout)
    assert found["good"][0] == 0, found["good"]
    assert found["host"][0] == 1 and "reference's host" in found["host"][1]
    assert found["token"][0] == 1 and "account bob" in found["token"][1]
    assert "ACCEPT_ACCOUNT_BOB" in found["token"][1], found["token"][1]
    assert found["setup"][0] == 1 and "REF_BASE" in found["setup"][1]
    alone = run_script("drafts", "check", tmp_path / "token.md", "--repo", repo, "--reference",
                       "ref", env=env)
    assert alone.returncode == 1 and alone.stderr.startswith("error:"), alone.stdout


def start_app(name: str):
    proc = subprocess.Popen([sys.executable, str(PAIR / f"{name}.py")],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc, proc.stdout.readline().strip().removeprefix("listening on ")


def test_fixture_pair_is_classified(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    env, _ = home_env(tmp_path)
    out, spec = tmp_path / "out", PAIR / "spec"
    registry = (spec / "departures.yaml").read_bytes()
    rebuild, rebuild_url = start_app("rebuild")
    reference, reference_url = start_app("reference")
    classes = {}
    try:
        proxy, base, ref_base = start_pair(repo, rebuild_url, reference_url, env,
                                           tmp_path / "p.jsonl")
        try:
            for name in ("spec-gap", "reference-defect", "departure", "build-defect"):
                draft = tmp_path / f"{name}.md"
                shutil.copy(PAIR / "drafts" / f"{name}.md", draft)
                assert run_script("finding_v1", "render", "--draft", draft).returncode == 0
                check = run_script("drafts", "check", draft, "--oracle", spec)
                assert check.returncode == 0, (name, check.stdout, check.stderr)
                results = []
                for side, url in (("rebuild", base), ("reference", ref_base)):
                    ran = run_script("finding_v1", "replay", "--draft", draft, "--base", url)
                    path = tmp_path / f"{name}.{side}.json"
                    path.write_text(ran.stdout, encoding="utf-8")
                    results.append(path)
                wrote = run_script("finding_v1", "write", "--repo", repo, "--out", out,
                                   "--draft", draft, "--oracle", spec,
                                   "--rebuild", results[0], "--reference", results[1])
                assert wrote.returncode == 0, (name, wrote.stderr)
                finding = json.loads(Path(wrote.stdout.strip()).read_text(encoding="utf-8"))
                classes[name] = (finding["class"], finding.get("departure"))
        finally:
            stop(proxy)
    finally:
        stop(rebuild, reference)
    assert classes == {
        "spec-gap": ("spec-gap", None),
        "reference-defect": ("reference-defect", None),
        "departure": ("accepted-departure", "D-001"),
        "build-defect": ("build-defect", None),
    }
    # Proposed, never written: the registry is the owner's.
    assert (spec / "departures.yaml").read_bytes() == registry
