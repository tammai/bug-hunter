import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from conftest import SCRIPTS, run_script

ORIGIN = "https://github.com/acme/shop.git"
TOKEN = "Bearer Zq8Wx7CeTk41"
TENANT = "acme-tenant-42"


def home_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    home = tmp_path / "home dir"
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    return env, home / ".bug-hunter" / "github.com" / "acme" / "shop" / "targets.json"


def write_targets(path: Path, targets) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(targets if isinstance(targets, str) else json.dumps(targets),
                    encoding="utf-8")


def start_stub(tmp_path: Path, rules: list[dict], port: int = 0):
    scenario = tmp_path / "stub.json"
    scenario.write_text(json.dumps(rules), encoding="utf-8")
    log = tmp_path / "stub log.jsonl"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPTS / "stub_server.py"), "--scenario", str(scenario),
         "--log", str(log), "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc, proc.stdout.readline().strip().removeprefix("listening on "), log


def start_proxy(repo, target, env, log, *extra):
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPTS / "live_proxy.py"), "--repo", str(repo), "--target", target,
         "--log", str(log), *extra],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    line = proc.stdout.readline().strip()
    assert line.startswith("listening on http://127.0.0.1:"), (line, proc.stderr.read())
    return proc, line.removeprefix("listening on ")


def stop(*procs) -> str:
    out = ""
    for proc in procs:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        out += stdout + stderr
    return out


def call(url, method="GET", body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read().decode()


def raw(base: str, request: bytes) -> bytes:
    host, port = base.removeprefix("http://").split(":")
    with socket.create_connection((host, int(port)), timeout=5) as sock:
        sock.sendall(request)
        return sock.recv(200).split(b"\r\n")[0]


def entries(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_targets_resolve_or_fail_cleanly(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    log = tmp_path / "proxy.jsonl"
    for target in ("http://localhost:5173", "http://127.0.0.1:8000/api", "http://[::1]:3000"):
        proc, _ = start_proxy(repo, target, env, log)
        stop(proc)

    def fails(target: str) -> None:
        result = run_script("live_proxy", "--repo", repo, "--target", target, "--log", log,
                            env=env)
        assert result.returncode == 1, (target, result.stdout)
        assert result.stderr.startswith("error:") and "Traceback" not in result.stderr, target

    fails("uat")  # no targets.json yet
    write_targets(targets, "{not json")
    fails("uat")
    write_targets(targets, {"uat": {"url": "https://uat.example.com"},
                            "ftp": {"url": "ftp://files.example.com"},
                            "typed": {"url": "https://uat.example.com", "writes": "yes"},
                            "accts": {"url": "https://uat.example.com", "accounts": ["alice"]}})
    proc, _ = start_proxy(repo, "uat", env, log)
    stop(proc)
    for target in ("prod", "https://uat.example.com", "https://example.com", "http://localhost",
                   "ftp", "typed", "accts", ""):
        fails(target)


def test_forwards_only_to_the_target(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [
        {"path": "/api/items", "responses": [
            {"status": 418, "headers": {"X-Upstream": "yes"}, "body": {"ok": 1}}]},
        {"path": "/api/go", "responses": [
            {"status": 302, "headers": {"Location": "https://example.com/elsewhere"}}]},
    ])
    write_targets(targets, {"uat": {"url": stub_base + "/api"}})
    proxy, base = start_proxy(repo, "uat", env, tmp_path / "proxy.jsonl")
    try:
        status, headers, body = call(base + "/items?page=2&q=a%20b")
        assert status == 418 and headers["X-Upstream"] == "yes" and json.loads(body) == {"ok": 1}
        status, headers, _ = call_no_redirect(base + "/go")
        assert status == 302 and headers["Location"] == "https://example.com/elsewhere"
        assert b" 400 " in raw(base, b"GET http://example.com/x HTTP/1.1\r\nHost: x\r\n\r\n")
        assert b" 400 " in raw(base, b"GET /../secret HTTP/1.1\r\nHost: x\r\n\r\n")
        assert b" 400 " in raw(base, b"GET /%2e%2e/secret HTTP/1.1\r\nHost: x\r\n\r\n")
    finally:
        stop(proxy, stub)
    seen = entries(stub_log)
    assert [(e["path"], e["query"]) for e in seen] == [
        ("/api/items", "page=2&q=a%20b"), ("/api/go", "")]


def call_no_redirect(url):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(url, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read().decode()


def test_accounts_are_added_and_never_logged(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [{"path": "/me", "responses": [{}]}])
    write_targets(targets, {"uat": {"url": stub_base, "accounts": {
        "alice": {"Authorization": TOKEN, "X-Tenant": TENANT}}}})
    proxy_log = tmp_path / "proxy.jsonl"
    proxy, base = start_proxy(repo, "uat", env, proxy_log)
    try:
        assert call(base + "/me", headers={"X-Bug-Hunter-Account": "alice"})[0] == 200
        assert call(base + "/me", headers={"X-Bug-Hunter-Account": "mallory"})[0] == 400
        assert call(base + "/me", headers={"Authorization": "Bearer invented"})[0] == 200
    finally:
        output = stop(proxy, stub)
    seen = entries(stub_log)
    assert len(seen) == 2
    first = {k.lower(): v for k, v in seen[0]["headers"].items()}
    assert first["x-tenant"] == TENANT and "authorization" in first
    assert "x-bug-hunter-account" not in first
    logged = proxy_log.read_text(encoding="utf-8")
    assert [e.get("account") for e in entries(proxy_log)][:1] == ["alice"]
    for secret in ("Zq8Wx7CeTk41", TENANT):
        assert secret not in logged and secret not in output, secret


def test_writes_only_where_allowed_and_logged(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [{"path": "/orders", "responses": [
        {"status": 201, "body": {"id": 7}}]}])
    write_targets(targets, {"uat": {"url": stub_base}})
    read_only_log = tmp_path / "ro.jsonl"
    proxy, base = start_proxy(repo, "uat", env, read_only_log)
    try:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            status, _, body = call(base + "/orders", method, b'{"qty": 1}',
                                   {"Content-Type": "application/json"})
            assert status == 403 and "error" in json.loads(body), method
        assert call(base + "/orders")[0] == 201
    finally:
        stop(proxy)
    assert [e["method"] for e in entries(stub_log)] == ["GET"]

    writes_log = tmp_path / "rw.jsonl"
    proxy, base = start_proxy(repo, stub_base, env, writes_log)  # localhost: writes allowed
    try:
        status, _, _ = call(base + "/orders?password=hunter2x", "POST",
                            b'{"qty": -1, "password": "hunter2x"}',
                            {"Content-Type": "application/json"})
        assert status == 201
    finally:
        stop(proxy, stub)
    assert entries(stub_log)[-1]["method"] == "POST"
    line = entries(writes_log)[-1]
    assert (line["method"], line["path"], line["status"]) == ("POST", "/orders", 201)
    assert "account" in line and "hunter2x" not in writes_log.read_text(encoding="utf-8")


def test_budget_and_rate(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, _ = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [{"path": "/x", "responses": [{}]}])
    proxy, base = start_proxy(repo, stub_base, env, tmp_path / "p.jsonl",
                              "--max-requests", "6", "--rate", "5")
    statuses: list[int] = []
    try:
        threads = [threading.Thread(target=lambda: statuses.append(call(base + "/x")[0]))
                   for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert call(base + "/x")[0] == 429
    finally:
        stop(proxy, stub)
    assert sorted(statuses) == [200] * 6
    times = sorted(e["time"] for e in entries(stub_log))
    assert len(times) == 6 and times[-1] - times[0] >= 0.9


def test_proxy_flags_are_checked(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, _ = home_env(tmp_path)
    for flag, value in (("--max-requests", "0"), ("--rate", "0"), ("--rate", "nan"),
                        ("--idle-exit", "0")):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "live_proxy.py"), "--repo", str(repo), "--target",
             "http://localhost:9", "--log", str(tmp_path / "l.jsonl"), flag, value],
            capture_output=True, text=True, env=env, timeout=10)
        assert result.returncode != 0 and "Traceback" not in result.stderr, (flag, value)
    started = time.monotonic()
    proc, _ = start_proxy(repo, "http://localhost:9", env, tmp_path / "l.jsonl",
                          "--idle-exit", "1")
    assert proc.wait(timeout=10) == 0 and time.monotonic() - started < 10


def test_bad_targets_fail_without_echoing_secrets(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    write_targets(targets, {
        "newline": {"url": "https://uat.example.com",
                    "accounts": {"alice": {"Authorization": "Bearer Kq7Lm2\r\nX-Evil: 1"}}},
        "latin": {"url": "https://uat.example.com",
                  "accounts": {"alice": {"Authorization": "Bearer Pp9Rr8…"}}},
        "badname": {"url": "https://uat.example.com",
                    "accounts": {"alice": {"Bad Header": "Vv5Ww6Xx"}}},
        "dashed": {"url": "https://uat.example.com", "accounts": {"qa-admin": {"X-A": "1"}}},
        "userinfo": {"url": "https://ops:Hh3Jj4@uat.example.com"},
    })
    for name in ("newline", "latin", "badname", "dashed", "userinfo"):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "live_proxy.py"), "--repo", str(repo), "--target",
             name, "--log", str(tmp_path / "l.jsonl"), "--check"],
            capture_output=True, text=True, env=env, timeout=10)
        assert result.returncode == 1 and result.stderr.startswith("error:"), name
        assert "Traceback" not in result.stderr, name
        for secret in ("Kq7Lm2", "Pp9Rr8", "Vv5Ww6Xx", "Hh3Jj4"):
            assert secret not in result.stderr + result.stdout, (name, secret)


def test_check_validates_without_listening(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    write_targets(targets, {"uat": {"url": "https://uat.example.com",
                                    "accounts": {"alice": {"Authorization": "Bearer Tt1Uu2"}}}})
    ok = run_script("live_proxy", "--repo", repo, "--target", "uat", "--log",
                    tmp_path / "l.jsonl", "--check", env=env)
    assert ok.returncode == 0 and "listening" not in ok.stdout
    assert "uat.example.com" not in ok.stdout and "Tt1Uu2" not in ok.stdout
    assert "alice" in ok.stdout
    bad = run_script("live_proxy", "--repo", repo, "--target", "prod", "--log",
                     tmp_path / "l.jsonl", "--check", env=env)
    assert bad.returncode == 1 and bad.stderr.startswith("error:")


def headers_of(url: str, method: str = "GET") -> tuple[list[str], dict]:
    import http.client
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
    conn.request(method, parts.path)
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return sorted(k.lower() for k, _ in resp.getheaders()), dict(resp.getheaders())


def test_responses_keep_target_headers_and_hide_tokens_and_url(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    stub_base = f"http://127.0.0.1:{port}"
    netloc = stub_base.removeprefix("http://")
    stub, stub_base, _ = start_stub(tmp_path, [
        {"path": "/plain", "responses": [{"status": 200, "body": "hello world"}]},
        {"path": "/echo", "responses": [{"status": 302, "headers": {
            "Location": stub_base + "/next", "X-Seen": TOKEN},
            "body": f"auth={TOKEN} tenant={TENANT} self={stub_base}/me host={netloc}"}]},
    ], port)
    write_targets(targets, {"uat": {"url": stub_base, "accounts": {
        "alice": {"Authorization": TOKEN, "X-Tenant": TENANT}}}})
    proxy, base = start_proxy(repo, "uat", env, tmp_path / "p.jsonl")
    try:
        direct, _ = headers_of(stub_base + "/plain")
        proxied, _ = headers_of(base + "/plain")
        assert proxied == direct
        _, head_direct = headers_of(stub_base + "/plain", "HEAD")
        _, head_proxied = headers_of(base + "/plain", "HEAD")
        assert head_proxied["Content-Length"] == head_direct["Content-Length"] == "11"
        status, headers, body = call_no_redirect_with(base + "/echo",
                                                      {"X-Bug-Hunter-Account": "alice"})
    finally:
        stop(proxy, stub)
    assert status == 302 and headers["Location"] == base + "/next"
    for secret in ("Zq8Wx7CeTk41", TENANT, netloc):
        assert secret not in body and secret not in json.dumps(headers), secret
    assert f"self={base}/me" in body


def call_no_redirect_with(url, headers):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read().decode()


def test_odd_paths_overrides_and_query_dots(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [{"path": "/x", "responses": [{}]}])
    write_targets(targets, {"uat": {"url": stub_base}})
    proxy_log = tmp_path / "p.jsonl"
    proxy, base = start_proxy(repo, "uat", env, proxy_log, "--max-requests", "1")
    try:
        assert b" 400 " in raw(base, "GET /café HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        assert call(base + "/x", headers={"X-HTTP-Method-Override": "DELETE"})[0] == 403
        assert call(base + "/x?_method=DELETE")[0] == 403
        assert call(base + "/x?file=../../etc/hosts")[0] == 200
    finally:
        output = stop(proxy, stub)
    assert "Traceback" not in output
    assert [e["query"] for e in entries(stub_log)] == ["file=../../etc/hosts"]
    notes = [e.get("note", "") for e in entries(proxy_log)]
    assert len(notes) == 4 and all(notes[:3])


def test_masks_every_form_of_an_account_value():
    import base64
    from urllib.parse import quote, quote_plus

    from live_proxy import _masker
    bearer = "ab/cd+ef=Gh12"
    password = "Pw7/Qq+Zz="
    basic = "Basic " + base64.b64encode(f"ops:{password}".encode()).decode()
    target = {"url": "https://uat.acme.test:8443", "accounts": {
        "alice": {"Authorization": f"Bearer {bearer}"}, "ops": {"Authorization": basic}}}
    mask = _masker(target, "http://127.0.0.1:9")
    forms = [bearer, bearer.replace("/", "\\/"), quote(bearer, safe=""), quote_plus(bearer),
             quote(bearer, safe="").lower(), basic.split()[1], f"ops:{password}", password,
             password.replace("/", "\\/"), quote_plus(password)]
    for form in forms:
        out = mask(f"echo [{form}] end".encode()).decode()
        assert form not in out and "<redacted>" in out, form


def test_masks_hosts_only_where_they_stand_alone():
    from live_proxy import _masker
    short = _masker({"url": "https://uat:8443/base", "accounts": {}}, "http://127.0.0.1:9")
    text = b"/actuator /api/orders https://uat:8443/x uat:8443/y"
    assert short(text) == b"/actuator /api/orders http://127.0.0.1:9/x <target>/y"
    dotted = _masker({"url": "https://uat.acme.test", "accounts": {}}, "http://127.0.0.1:9")
    assert dotted(b"host=uat.acme.test; xuat.acme.tests") == b"host=<target>; xuat.acme.tests"


def test_compressed_responses_are_refused(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, _ = start_stub(tmp_path, [{"path": "/z", "responses": [
        {"status": 200, "headers": {"Content-Encoding": "gzip"}, "body": "not really gzip"}]}])
    write_targets(targets, {"uat": {"url": stub_base}})
    proxy, base = start_proxy(repo, "uat", env, tmp_path / "p.jsonl")
    try:
        status, _, body = call(base + "/z")
    finally:
        stop(proxy, stub)
    assert status == 502 and "not really gzip" not in body
