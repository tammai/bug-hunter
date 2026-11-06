import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

from conftest import SCRIPTS, run_script


def start(tmp_path, scenario):
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    log = tmp_path / "requests log.jsonl"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPTS / "stub_server.py"), "--scenario", str(path), "--log",
         str(log)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = proc.stdout.readline().strip()
    assert line.startswith("listening on http://127.0.0.1:"), line
    return proc, line.removeprefix("listening on "), log


def call(url, method="GET", body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read().decode()


def test_serves_scripted_responses_and_logs_requests(tmp_path):
    proc, base, log = start(tmp_path, [
        {"method": "POST", "path": "/v1/charges", "responses": [
            {"status": 429, "headers": {"Retry-After": "1"}, "body": {"error": "rate"}},
            {"status": 200, "body": {"id": "ch_1"}}]},
        {"path": "/slow", "responses": [{"status": 200, "body": "ok", "delay": 0.5}]},
        {"path": "/drop", "responses": [{"close": True}]},
    ])
    try:
        status, headers, body = call(base + "/v1/charges", "POST", b'{"amount": 5}',
                                     {"Authorization": "Bearer abc", "X-Api-Token": "t1",
                                      "Content-Type": "application/json"})
        assert status == 429 and headers["Retry-After"] == "1"
        assert json.loads(body) == {"error": "rate"}
        assert call(base + "/v1/charges", "POST", b"{}")[0] == 200
        assert json.loads(call(base + "/v1/charges", "POST", b"{}")[2]) == {"id": "ch_1"}

        started = time.monotonic()
        assert call(base + "/slow")[2] == "ok"
        assert time.monotonic() - started >= 0.45

        try:
            call(base + "/drop")
            raise AssertionError("expected a dropped connection")
        except (urllib.error.URLError, ConnectionError, OSError):
            pass

        status, _, body = call(base + "/nowhere?x=1")
        assert status == 404 and "no scenario" in json.loads(body)["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    first = entries[0]
    assert first["method"] == "POST" and first["path"] == "/v1/charges"
    assert first["body"] == '{"amount": 5}'
    lowered = {k.lower(): v for k, v in first["headers"].items()}
    assert lowered["authorization"] == "<redacted>" and lowered["x-api-token"] == "<redacted>"
    assert "abc" not in log.read_text(encoding="utf-8")
    assert any(e["path"] == "/nowhere" and e["query"] == "x=1" for e in entries)
    assert sum(e["path"] == "/v1/charges" for e in entries) == 3


def test_bad_scenarios_fail_cleanly(tmp_path):
    for name, text in (("bad.json", "{not json"),
                       ("nopath.json", json.dumps([{"responses": [{"status": 200}]}])),
                       ("notobj.json", json.dumps([{"path": "/a", "responses": [5]}])),
                       ("notlist.json", json.dumps({"path": "/a"}))):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        result = run_script("stub_server", "--scenario", path, "--log", tmp_path / "l.jsonl")
        assert result.returncode == 1, name
        assert "Traceback" not in result.stderr and len(result.stderr.strip().splitlines()) == 1


def test_secrets_in_query_and_body_are_redacted_and_big_bodies_read(tmp_path):
    import http.client
    proc, base, log = start(tmp_path, [
        {"method": "POST", "path": "/token", "responses": [{"status": 200, "body": "ok"}]},
        {"path": "/q", "responses": [{"status": 200}]},
        {"method": "POST", "path": "/upload", "responses": [{"status": 201}]},
    ])
    try:
        assert call(base + "/q?api_key=Zq9TxW2v&x=1")[0] == 200
        call(base + "/token", "POST", b"client_secret=Ab12Cd34&grant_type=client_credentials",
             {"Content-Type": "application/x-www-form-urlencoded"})
        call(base + "/token", "POST", b'{"access_token": "Tk9Lm8Np", "n": 1}',
             {"Content-Type": "application/json"})
        assert call(base + "/upload", "POST", b"x" * 200_000)[0] == 201
        host, port = base.removeprefix("http://").split(":")
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.request("POST", "/upload", body=iter([b"chunk-one,", b"chunk-two"]),
                     encode_chunked=True)
        assert conn.getresponse().status == 201
        conn.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    text = log.read_text(encoding="utf-8")
    for secret in ("Zq9TxW2v", "Ab12Cd34", "Tk9Lm8Np"):
        assert secret not in text, secret
    entries = [json.loads(line) for line in text.splitlines()]
    assert any(e["query"] == "api_key=<redacted>&x=1" for e in entries)
    uploads = [e for e in entries if e["path"] == "/upload"]
    assert uploads[0]["body_bytes"] == 200_000 and len(uploads[0]["body"]) <= 65536
    assert uploads[1]["body"] == "chunk-one,chunk-two"


def test_reset_truncate_head_and_header_override(tmp_path):
    import http.client
    proc, base, _ = start(tmp_path, [
        {"path": "/reset", "responses": [{"reset": True}]},
        {"path": "/cut", "responses": [{"status": 200, "body": "0123456789", "truncate": 4}]},
        {"path": "/h", "responses": [{"status": 200, "body": "hello",
                                      "headers": {"Content-Type": "text/html"}}]},
    ])
    host, port = base.removeprefix("http://").split(":")
    try:
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.request("GET", "/reset")
        try:
            conn.getresponse()
            raise AssertionError("expected a reset")
        except (ConnectionResetError, http.client.RemoteDisconnected, BrokenPipeError):
            pass
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.request("GET", "/cut")
        resp = conn.getresponse()
        try:
            resp.read()
            raise AssertionError("expected a truncated body")
        except http.client.IncompleteRead as err:
            assert err.partial == b"0123"
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.request("HEAD", "/h")
        resp = conn.getresponse()
        assert resp.read() == b"" and resp.getheader("Content-Type") == "text/html"
        assert len(resp.headers.get_all("Content-Type")) == 1
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_badly_typed_scenarios_fail_at_start(tmp_path):
    for n, rule in enumerate(({"path": "/a", "method": 5, "responses": [{}]},
                              {"path": "/a", "responses": [{"status": "oops"}]},
                              {"path": "/a", "responses": [{"headers": ["x"]}]},
                              {"path": "/a", "responses": [{"delay": "slow"}]},
                              {"path": "/a", "responses": [{"truncate": -1}]})):
        path = tmp_path / f"s{n}.json"
        path.write_text(json.dumps([rule]), encoding="utf-8")
        result = run_script("stub_server", "--scenario", path, "--log", tmp_path / "l.jsonl")
        assert result.returncode == 1 and "Traceback" not in result.stderr, rule
