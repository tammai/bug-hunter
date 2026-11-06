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


def test_round_two_redaction_encoding_and_robustness(tmp_path):
    import socket
    proc, base, log = start(tmp_path, [
        {"method": "POST", "path": "/in", "responses": [{"status": 200, "body": "ok"}]},
        {"path": "/q", "responses": [{"status": 204, "body": {"ok": True}}]},
    ])
    host, port = base.removeprefix("http://").split(":")
    big = json.dumps({"pad": "x" * 70_000, "access_token": "Tk9Lm8Np"}).encode()
    try:
        call(base + "/in", "POST", big, {"Content-Type": "application/json"})
        call(base + "/in", "POST", b'{"client_secret": "Ab12Cd34"}', {"Content-Type": "text/plain"})
        multipart = (b'--B\r\nContent-Disposition: form-data; name="client_secret"\r\n\r\n'
                     b"Mp7Qr6St\r\n--B--\r\n")
        call(base + "/in", "POST", multipart, {"Content-Type": "multipart/form-data; boundary=B"})
        call(base + "/in", "POST", b'{"api_key":"Nd5Ws4Xe"}\n{"n":1}\n',
             {"Content-Type": "application/x-ndjson"})
        status, _, body = call(base + "/q?path=/a/b&q=a%20b&flag")
        assert status == 204 and body == ""

        raw = socket.create_connection((host, int(port)), timeout=5)
        raw.sendall(b"POST /in HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n")
        reply = raw.recv(200)
        raw.close()
        assert reply.startswith(b"HTTP/1.") and b" 400 " in reply.split(b"\r\n")[0]
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    text = log.read_text(encoding="utf-8")
    for secret in ("Tk9Lm8Np", "Ab12Cd34", "Mp7Qr6St", "Nd5Ws4Xe"):
        assert secret not in text, secret
    entries = [json.loads(line) for line in text.splitlines()]
    assert any(e["query"] == "path=/a/b&q=a%20b&flag" for e in entries)
    assert any("malformed" in e.get("note", "") for e in entries)


def test_non_finite_and_boolean_values_fail_at_start(tmp_path):
    for n, text in enumerate(('[{"path": "/a", "responses": [{"truncate": true}]}]',
                              '[{"path": "/a", "responses": [{"delay": Infinity}]}]',
                              '[{"path": "/a", "responses": [{"delay": NaN}]}]')):
        path = tmp_path / f"s{n}.json"
        path.write_text(text, encoding="utf-8")
        result = run_script("stub_server", "--scenario", path, "--log", tmp_path / "l.jsonl")
        assert result.returncode == 1 and "Traceback" not in result.stderr, text


def test_structured_redaction_fails_closed(tmp_path):
    proc, base, log = start(tmp_path, [
        {"method": "POST", "path": "/in", "responses": [{"status": 200, "body": "ok"}]},
        {"path": "/q", "responses": [{"status": 200}]},
    ])
    secrets = ("Sk1Zq9Xw", "K1zz9Qpl", "Ab3Cd4Ef", "Zz9Yy8Xx", "Hu9nter2", "Tq8Rs7Uv",
               "Qa1Ws2Ed", "Ed3Rf4Tg", "Ml7Nk8Op", "Line2Zq9", "Un9Qt8Ed", "Bg5Hn6Jm")
    try:
        call(base + "/in", "POST", json.dumps({
            "secrets": {"stripe": "Sk1Zq9Xw"}, "api_keys": ["K1zz9Qpl"], "Auth Token": "Ab3Cd4Ef",
            "pad": "x" * 70_000}).encode(), {"Content-Type": "application/json"})
        call(base + "/in", "POST", json.dumps({"payload": '{"token": "Zz9Yy8Xx"}'}).encode(),
             {"Content-Type": "application/json"})
        call(base + "/in", "POST", b"user[password]=Hu9nter2&user%5Btoken%5D=Tq8Rs7Uv&n=1",
             {"Content-Type": "application/x-www-form-urlencoded"})
        call(base + "/q?user[token]=Qa1Ws2Ed&api%5Fkey=Ed3Rf4Tg&x=1")
        multipart = (b'--B\r\nContent-Disposition: form-data; name="client_secret"\r\n\r\n'
                     b"Ml7Nk8Op\r\nLine2Zq9\r\n--B\r\n"
                     b"Content-Disposition: form-data; name=token\r\n\r\nUn9Qt8Ed\r\n--B--\r\n")
        call(base + "/in", "POST", multipart, {"Content-Type": "multipart/form-data; boundary=B"})
        call(base + "/in", "POST", b"note: the password is Bg5Hn6Jm",
             {"Content-Type": "text/plain"})
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    text = log.read_text(encoding="utf-8")
    for secret in secrets:
        assert secret not in text, secret
    entries = [json.loads(line) for line in text.splitlines()]
    assert any(e["path"] == "/q" and e["query"].endswith("&x=1") for e in entries)
    assert any("withheld" in e["body"] for e in entries)


def test_limits_statuses_and_idle_exit(tmp_path):
    import socket
    for n, text in enumerate(('[{"path": "/a", "responses": [{"delay": 1' + "0" * 400 + '}]}]',
                              '[{"path": "/a", "responses": [{"delay": 1e300}]}]',
                              '[{"path": "/a", "responses": [{"delay": 4000}]}]',
                              '[{"path": "/a", "responses": [{"status": 100}]}]')):
        path = tmp_path / f"s{n}.json"
        path.write_text(text, encoding="utf-8")
        result = run_script("stub_server", "--scenario", path, "--log", tmp_path / "l.jsonl")
        assert result.returncode == 1 and "Traceback" not in result.stderr, n

    proc, base, log = start(tmp_path, [{"path": "/e", "responses": [{"status": 204}]}])
    host, port = base.removeprefix("http://").split(":")
    try:
        status, headers, _ = call(base + "/e")
        assert status == 204 and "Content-Length" not in headers
        raw = socket.create_connection((host, int(port)), timeout=5)
        raw.sendall(b"POST /e HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n"
                    b"4\r\nabcd\r\nfffffffffff\r\n")
        assert b" 400 " in raw.recv(200).split(b"\r\n")[0]
        raw.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    bad = [e for e in entries if "malformed" in e.get("note", "")]
    assert bad and bad[0]["body"] == "abcd" and bad[0]["body_bytes"] == 4

    path = tmp_path / "idle.json"
    path.write_text(json.dumps([{"path": "/a", "responses": [{}]}]), encoding="utf-8")
    idle = subprocess.Popen([sys.executable, str(SCRIPTS / "stub_server.py"), "--scenario",
                             str(path), "--log", str(tmp_path / "i.jsonl"), "--idle-exit", "1"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert idle.wait(timeout=10) == 0


def test_escaped_secrets_slow_answers_and_negative_chunks(tmp_path):
    import socket
    path = tmp_path / "s.json"
    path.write_text(json.dumps([
        {"method": "POST", "path": "/in", "responses": [{"status": 200}]},
        {"path": "/slow", "responses": [{"status": 200, "body": "late", "delay": 2.5}]},
    ]), encoding="utf-8")
    log = tmp_path / "l.jsonl"
    proc = subprocess.Popen([sys.executable, str(SCRIPTS / "stub_server.py"), "--scenario",
                             str(path), "--log", str(log), "--idle-exit", "1"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    base = proc.stdout.readline().strip().removeprefix("listening on ")
    host, port = base.removeprefix("http://").split(":")
    try:
        call(base + "/in", "POST", b'{"x": "pa\\u0073sword Hu9nter2"}',
             {"Content-Type": "application/json"})
        call(base + "/in", "POST", b'{"payload": "{\\"\\u0074oken\\": \\"Zq8Wx7Ce\\"}"}',
             {"Content-Type": "application/json"})
        assert call(base + "/slow")[2] == "late"
        raw = socket.create_connection((host, int(port)), timeout=5)
        raw.sendall(b"POST /in HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n-1\r\n")
        assert b" 400 " in raw.recv(200).split(b"\r\n")[0]
        raw.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    text = log.read_text(encoding="utf-8")
    assert "Hu9nter2" not in text and "Zq8Wx7Ce" not in text


def test_encoded_secret_words_and_broken_chunks(tmp_path):
    import socket
    proc, base, log = start(tmp_path, [{"method": "POST", "path": "/in",
                                        "responses": [{"status": 200}]}])
    host, port = base.removeprefix("http://").split(":")
    try:
        call(base + "/in", "POST", b'{"note": "%74oken=Zz1Yy2"}',
             {"Content-Type": "application/json"})
        call(base + "/in", "POST", b"a=%2574oken%3DQq7Ww8",
             {"Content-Type": "application/x-www-form-urlencoded"})
        call(base + "/in?q=%2574oken%3DRr5Tt6", "POST", b"")
        for chunks in (b"14\r\npa\\u0073sword Kk4Jj3\r\nzz\r\n", b"4\r\nabcd\r\n\r\n"):
            raw = socket.create_connection((host, int(port)), timeout=5)
            raw.sendall(b"POST /in HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n"
                        + chunks)
            assert b" 400 " in raw.recv(200).split(b"\r\n")[0], chunks
            raw.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    text = log.read_text(encoding="utf-8")
    for secret in ("Zz1Yy2", "Qq7Ww8", "Rr5Tt6", "Kk4Jj3"):
        assert secret not in text, secret


def test_idle_exit_must_be_positive(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps([{"path": "/a", "responses": [{}]}]), encoding="utf-8")
    for value in ("0", "-1", "nan"):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "stub_server.py"), "--scenario", str(path),
             "--log", str(tmp_path / "l.jsonl"), "--idle-exit", value],
            capture_output=True, text=True, timeout=10)
        assert result.returncode != 0 and "Traceback" not in result.stderr, value
        assert "idle-exit" in result.stderr, value
