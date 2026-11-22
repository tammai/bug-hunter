import base64
import json
import os
import re
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


def test_a_path_that_climbs_after_repeated_decoding_is_refused(make_repo, tmp_path):
    # A target or front end that decodes twice reads `%252e%252e` as `..`.
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [
        {"path": "/api/items/100%25", "responses": [{"body": {"ok": 1}}]}])
    write_targets(targets, {"uat": {"url": stub_base + "/api"}})
    proxy, base = start_proxy(repo, "uat", env, tmp_path / "proxy.jsonl")
    climbs = ["/%252e%252e/x", "/%25252e%25252e/x", "/%252E%252E/x", "/..%252fx",
              "/%255c..%255cx", "/a/%2525252e%2525252e/x"]
    try:
        answers = {path: raw(base, f"GET {path} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
                   for path in climbs}
        status, _, body = call(base + "/items/100%25")
    finally:
        stop(proxy, stub)
    for path, answer in answers.items():
        assert b" 400 " in answer, (path, answer)
    assert status == 200 and json.loads(body) == {"ok": 1}
    assert len(entries(stub_log)) == 1


def test_every_spelling_of_a_dot_segment_leaves_the_base():
    # Servers end a segment's name at `;`, `?` or `#`, and some trim trailing dots and spaces.
    from live_proxy import _leaves_base

    for path in ("/..;/x", "/..;a=b/x", "/%2e%2e%3b/x", "/..%3fx", "/..%23x",
                 "/%252e%252e%253fx", "/.../x", "/.. /x", "/..%20/x", "/.%20/x", "/..\t/x",
                 "/%u002e%u002e/x", "/%U002E%U002E/x", "/a/%252e%252e%252e/x",
                 "/%c0%ae%c0%ae/x", "/%C0%AE./x", "/..%00/x", "/%00", "/%ef%bc%8e%ef%bc%8e/x",
                 "/%25ef%25bc%258e%25ef%25bc%258e/x", "/%e0%80%ae%e0%80%ae/x", "/..%e0%80%afx",
                 "/%f0%80%80%ae%f0%80%80%ae/x", "/%e0%2580%25ae%e0%2580%25ae/x", "/a%f5b",
                 "/a%ffb"):
        assert _leaves_base(path), path
    for path in ("/items/100%25", "/items/a;b", "/v1.2/x", "/file.tar.gz", "/.well-known/x",
                 "/a/b?q=..", "/", "/a..b/c", "/..a/x", "/caf%C3%A9", "/%E6%97%A5%E6%9C%AC",
                 "/%F0%9F%98%80", "/caf%e9", "/%e0%a0%80", "/%f0%90%80%80"):
        assert not _leaves_base(path), path


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
             re.sub(r"%[0-9A-F]{2}", lambda m: m.group().lower(), quote(bearer, safe="")),
             basic.split()[1], f"ops:{password}", password,
             password.replace("/", "\\/"), quote_plus(password)]
    for form in forms:
        out = mask(f"echo [{form}] end".encode()).decode()
        assert form not in out and "<redacted>" in out, form


def test_masks_hosts_with_the_scans_patterns_and_plain_names_only_with_a_port():
    from live_proxy import _masker
    short = _masker({"url": "https://uat:8443/base", "accounts": {}}, "http://127.0.0.1:9")
    text = b"/actuator /api/orders https://uat:8443/x uat:8443/y"
    assert short(text) == b"/actuator /api/orders http://127.0.0.1:9/x <target>/y"
    dotted = _masker({"url": "https://uat.acme.test", "accounts": {}}, "http://127.0.0.1:9")
    # The leak scan's patterns, so a host inside a longer word is hidden too.
    assert dotted(b"host=uat.acme.test; xuat.acme.tests") == b"host=<target>; x<target>s"


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


def test_masking_is_exact_and_covers_more_logins():
    import base64
    from urllib.parse import quote

    from live_proxy import _masker
    word = "Hunter2Pass"
    utf8_pw = "pässword9X"
    target = {"url": "https://[fd00::1]", "accounts": {
        "ops": {"Authorization": "Basic " + base64.b64encode(f"ops:{word}".encode()).decode()},
        "dev": {"Authorization": "Basic  " + base64.b64encode(
            f"dev:{utf8_pw}".encode()).decode()},
        "api": {"Authorization": "Bearer ab/cd+ef=Gh12"}}}
    mask = _masker(target, "http://127.0.0.1:9")
    assert mask(f"{word} {word.upper()} {word.lower()}".encode()) == \
        f"<redacted> {word.upper()} {word.lower()}".encode()
    assert utf8_pw.encode() not in mask(f"pw={utf8_pw}".encode())
    lower_hex = re.sub(r"%[0-9A-F]{2}", lambda m: m.group().lower(),
                       quote("ab/cd+ef=Gh12", safe=""))
    assert lower_hex.encode() not in mask(lower_hex.encode())
    assert mask(b"host fd00::1 here") == b"host <target> here"


def test_check_warns_about_word_passwords(make_repo, tmp_path):
    import base64
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    basic = "Basic " + base64.b64encode(b"ops:letmeinnow").decode()
    write_targets(targets, {"uat": {"url": "https://uat.example.com",
                                    "accounts": {"ops": {"Authorization": basic}}}})
    ok = run_script("live_proxy", "--repo", repo, "--target", "uat", "--log",
                    tmp_path / "l.jsonl", "--check", env=env)
    assert ok.returncode == 0 and "warning" in ok.stdout + ok.stderr
    assert "letmeinnow" not in ok.stdout + ok.stderr


def test_compressed_bodies_refused_without_echo_but_bodiless_replies_pass(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, _ = start_stub(tmp_path, [
        {"path": "/z", "responses": [
            {"status": 200, "headers": {"Content-Encoding": "x-Zz9Yy8"}, "body": "data"}]},
        {"path": "/empty", "responses": [{"status": 204, "headers": {"Content-Encoding": "gzip"}}]},
    ])
    write_targets(targets, {"uat": {"url": stub_base}})
    log = tmp_path / "p.jsonl"
    proxy, base = start_proxy(repo, "uat", env, log)
    try:
        status, _, body = call(base + "/z")
        head_status = call(base + "/z", "HEAD")[0]
        empty_status = call(base + "/empty")[0]
    finally:
        stop(proxy, stub)
    assert status == 502 and "Zz9Yy8" not in body
    assert "Zz9Yy8" not in log.read_text(encoding="utf-8")
    assert head_status == 200 and empty_status == 204


def test_masking_round_five_forms():
    import base64

    from live_proxy import _masker
    latin = "p\u00e4sswordX"
    dotted = _masker({"url": "https://uat.acme.test", "accounts": {
        "ops": {"Authorization": "Basic " + base64.b64encode(
            f"ops:{latin}".encode("latin-1")).decode()},
        "api": {"Authorization": "Bearer ab/cd+ef=Gh12"}}}, "http://127.0.0.1:9")
    assert dotted(b"Host:uat.acme.test") == b"Host:<target>"
    assert latin.encode("latin-1") not in dotted(b"pw=" + latin.encode("latin-1"))
    for html_form in ("ab/cd&#43;ef&#61;Gh12", "ab&#47;cd&#43;ef&#61;Gh12",
                      "ab/cd&#x2B;ef&#x3D;Gh12"):
        assert html_form.encode() not in dotted(html_form.encode()), html_form
    v6 = _masker({"url": "https://[fd00::1]", "accounts": {}}, "http://127.0.0.1:9")
    assert v6(b"at fd00::1 and 2001:fd00::1 end") == b"at <target> and 2001:<target> end"
    v4 = _masker({"url": "https://10.0.0.5:8443", "accounts": {}}, "http://127.0.0.1:9")
    assert v4(b"peer ::ffff:10.0.0.5 up") == b"peer <target> up"
    assert b"Gh12" not in dotted(b"ab/cd&#x2b;ef&#x3d;Gh12")


def test_check_warns_about_short_passwords(make_repo, tmp_path):
    import base64
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    write_targets(targets, {"uat": {"url": "https://uat.example.com", "accounts": {
        "ops": {"Authorization": "Basic " + base64.b64encode(b"ops:Ab1").decode()}}}})
    ok = run_script("live_proxy", "--repo", repo, "--target", "uat", "--log",
                    tmp_path / "l.jsonl", "--check", env=env)
    out = ok.stdout + ok.stderr
    assert ok.returncode == 0 and "shorter than 6" in out and "will show <redacted>" not in out


def test_no_short_password_warning_for_key_only_basic(make_repo, tmp_path):
    import base64
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    write_targets(targets, {"uat": {"url": "https://uat.example.com", "accounts": {
        "api": {"Authorization": "Basic " + base64.b64encode(b"sk_test_Rr4Tt5Yy6:").decode()}}}})
    ok = run_script("live_proxy", "--repo", repo, "--target", "uat", "--log",
                    tmp_path / "l.jsonl", "--check", env=env)
    assert ok.returncode == 0 and "warning" not in ok.stdout + ok.stderr


MINT = """import json, pathlib, sys, time
count = pathlib.Path("count.txt")
n = int(count.read_text()) + 1 if count.exists() else 1
count.write_text(str(n))
time.sleep({sleep})
if n >= {fail_at}:
    print("sign-in failed for alice: Hh7Jj8Kk", file=sys.stderr)
    print("Hh7Jj8Kk")
    sys.exit(3)
print(json.dumps({{"alice": {{"X-Seat": f"sess-Kq9{{n}}Zx"}}}}))
"""


def mint_target(targets: Path, url: str, fail_at: int = 99, sleep: float = 0,
                **extra) -> Path:
    """A target whose refresh command mints sess-Kq9<n>Zx on its n-th run; returns its counter."""
    targets.parent.mkdir(parents=True, exist_ok=True)
    (targets.parent / "mint.py").write_text(MINT.format(fail_at=fail_at, sleep=sleep),
                                            encoding="utf-8")
    write_targets(targets, {"uat": {"url": url, "refresh": [sys.executable, "mint.py"],
                                    **extra}})
    return targets.parent / "count.txt"


def runs(counter: Path) -> int:
    return int(counter.read_text()) if counter.exists() else 0


def sent_seats(stub_log: Path) -> list:
    return [{k.lower(): v for k, v in e["headers"].items()}.get("x-seat")
            for e in entries(stub_log)]


def test_refresh_mints_accounts_at_start(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [{"path": "/me", "responses": [
        {"body": "your old key static-Aa1Dd2"}]}])
    short = "Basic " + base64.b64encode(b"carol:abc").decode()
    # A static Alice that the minted alice replaces: one account, its old value still masked.
    counter = mint_target(targets, stub_base, accounts={
        "Alice": {"X-Seat": "static-Aa1Dd2"}, "bob": {"X-Seat": "static-Bb5Cc6"},
        "carol": {"Authorization": short}})
    check = run_script("live_proxy", "--repo", repo, "--target", "uat", "--log",
                       tmp_path / "l.jsonl", "--check", env=env)
    assert check.returncode == 0, check.stderr
    assert "alice" in check.stdout and "bob" in check.stdout and "Kq9" not in check.stdout
    assert "Alice" not in check.stdout
    assert check.stdout.count("shorter than 6") == 1 and "account 's" not in check.stdout
    assert runs(counter) == 1
    proxy, base = start_proxy(repo, "uat", env, tmp_path / "proxy.jsonl")
    try:
        status, _, body = call(base + "/me", headers={"X-Bug-Hunter-Account": "alice"})
        assert status == 200 and "static-Aa1Dd2" not in body
        assert call(base + "/me", headers={"X-Bug-Hunter-Account": "bob"})[0] == 200
    finally:
        stop(proxy, stub)
    assert sent_seats(stub_log) == ["sess-Kq92Zx", "static-Bb5Cc6"]


def test_401_refreshes_and_retries_once(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [
        {"path": "/me", "responses": [
            {"status": 401}, {"status": 401},
            {"body": "old sess-Kq91Zx new sess-Kq92Zx", "headers": {"X-Echo": "sess-Kq91Zx"}},
            {"status": 401}, {"status": 401}]},
        {"path": "/bob", "responses": [{"status": 401}]}])
    counter = mint_target(targets, stub_base, accounts={"bob": {"X-Seat": "static-Bb5Cc6"}})
    proxy_log = tmp_path / "proxy.jsonl"
    proxy, base = start_proxy(repo, "uat", env, proxy_log, "--max-requests", "4",
                              "--refresh-gap", "1")
    alice = {"X-Bug-Hunter-Account": "alice"}
    try:
        # Just minted at start: a 401 now is not an expired token.
        assert call(base + "/me", headers=alice)[0] == 401 and runs(counter) == 1
        time.sleep(1.2)
        # A static account's 401 can't be fixed by minting.
        assert call(base + "/bob", headers={"X-Bug-Hunter-Account": "bob"})[0] == 401
        assert runs(counter) == 1
        status, headers, body = call(base + "/me", headers=alice)
        assert status == 200 and runs(counter) == 2
        assert "Kq9" not in body and "Kq9" not in json.dumps(headers)
        # Within the gap since the last refresh: no new mint; the retry's 401 is passed through.
        assert call(base + "/me", headers=alice)[0] == 401 and runs(counter) == 2
        # Four slots used by four requests, the retry included in its request's.
        assert call(base + "/me", headers=alice)[0] == 429
    finally:
        output = stop(proxy, stub)
    assert sent_seats(stub_log) == ["sess-Kq91Zx", "static-Bb5Cc6", "sess-Kq91Zx",
                                    "sess-Kq92Zx", "sess-Kq92Zx"]
    logged = entries(proxy_log)
    assert [(e["status"], e.get("note", ""), e.get("forwarded", False)) for e in logged] == [
        (401, "", True), (401, "", True), (200, "retried after token refresh", True),
        (401, "", True), (429, "request budget used up", False)]
    assert "Kq9" not in proxy_log.read_text(encoding="utf-8") and "Kq9" not in output


def test_concurrent_401s_share_one_refresh(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    echo = {"headers": {"X-Echo": "sess-Kq92Zx"}, "body": "sess-Kq92Zx"}
    stub, stub_base, _ = start_stub(tmp_path, [{"path": "/me", "responses": [
        {"status": 401}, {"status": 401}, echo]}])
    counter = mint_target(targets, stub_base, sleep=0.3)
    proxy, base = start_proxy(repo, "uat", env, tmp_path / "proxy.jsonl", "--refresh-gap",
                              "0", "--rate", "2")
    results = []
    started = time.monotonic()
    threads = [threading.Thread(target=lambda: results.append(
        call(base + "/me", headers={"X-Bug-Hunter-Account": "alice"}))) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
    finally:
        stop(proxy, stub)
    elapsed = time.monotonic() - started
    assert sorted(r[0] for r in results) == [200, 200] and runs(counter) == 2
    assert not any("Kq9" in r[2] or "Kq9" in json.dumps(r[1]) for r in results)
    # Four sends at 2 a second: the retries wait their turn under the rate.
    assert elapsed >= 1.4


def without_cwd_lookup_guard(env: dict) -> dict:
    return {k: v for k, v in env.items() if k.lower() != "nodefaultcurrentdirectoryinexepath"}


def test_refresh_failures_are_one_line(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    folder = targets.parent
    folder.mkdir(parents=True, exist_ok=True)
    scripts = {
        "exits.py": "import sys; print('Hh7Jj8Kk'); print('Hh7Jj8Kk', file=sys.stderr); "
                    "sys.exit(2)",
        "notjson.py": "print('token Hh7Jj8Kk')",
        "deep.py": "print('[' * 200000)",
        "badkey.py": "import json; print(json.dumps({'Hh7Jj8Kk.x': {}}))",
    }
    for name, code in scripts.items():
        (folder / name).write_text(code, encoding="utf-8")
    # A program planted in the hunted repo, which is the proxy's current folder.
    planted = Path(repo) / ("plantedpy" + Path(sys.executable).suffix)
    planted.write_bytes(Path(sys.executable).read_bytes())
    planted.chmod(0o755)  # PATH lookup on POSIX skips files that aren't executable
    entries_ = {name.removesuffix(".py"): {"url": "https://uat.example.com",
                                           "refresh": [sys.executable, name]}
                for name in scripts}
    entries_["missing"] = {"url": "https://uat.example.com",
                           "refresh": ["no-such-program-Hh7Jj8Kk"]}
    entries_["planted"] = {"url": "https://uat.example.com",
                           "refresh": ["plantedpy", "-c", "open('ran', 'w')"]}
    entries_["folder"] = {"url": "https://uat.example.com", "refresh": [str(folder)]}
    write_targets(targets, entries_)
    # The repo on PATH, as an activated virtualenv puts it, and the proxy run from elsewhere.
    on_path = dict(without_cwd_lookup_guard(env),
                   PATH=str(repo) + os.pathsep + env.get("PATH", ""))
    for name in entries_:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "live_proxy.py"), "--repo", str(repo), "--target",
             name, "--log", str(tmp_path / "l.jsonl"), "--check"],
            capture_output=True, text=True, timeout=90,
            env=on_path if name == "planted" else without_cwd_lookup_guard(env),
            cwd=tmp_path if name == "planted" else repo)
        assert result.returncode == 1, (name, result.stdout)
        assert result.stderr.startswith(f"error: {name}: ") and result.stderr.count("\n") == 1
        assert "Traceback" not in result.stderr, name
        assert "Hh7Jj8Kk" not in result.stderr + result.stdout, name
        assert ("hunted repo" in result.stderr) == (name == "planted"), (name, result.stderr)
    assert not (Path(repo) / "ran").exists() and not (tmp_path / "ran").exists()


def test_failed_refresh_mid_run_passes_401_through(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, _ = start_stub(tmp_path, [{"path": "/me", "responses": [
        {"status": 401}, {"status": 401}, {}]}])
    counter = mint_target(targets, stub_base, fail_at=2)
    proxy_log = tmp_path / "proxy.jsonl"
    proxy, base = start_proxy(repo, "uat", env, proxy_log, "--refresh-gap", "1")
    alice = {"X-Bug-Hunter-Account": "alice"}
    try:
        time.sleep(1.2)  # past the gap since the start-up mint, so the first 401 mints; it fails
        assert call(base + "/me", headers=alice)[0] == 401
        assert call(base + "/me", headers=alice)[0] == 401  # throttled: the last mint failed
        assert call(base + "/me", headers=alice)[0] == 200
    finally:
        output = stop(proxy, stub)
    assert runs(counter) == 2
    assert [(e["status"], e.get("note", "")) for e in entries(proxy_log)] == [
        (401, "token refresh failed"), (401, "token refresh failed"), (200, "")]
    assert "Hh7Jj8Kk" not in proxy_log.read_text(encoding="utf-8") + output


def test_refresh_shape_checked_and_not_run_by_load(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    counter = mint_target(targets, "https://uat.example.com")
    draft = tmp_path / "draft.md"
    draft.write_text("# A draft\n", encoding="utf-8")
    checked = run_script("drafts", "check", draft, "--repo", repo, "--target", "uat", env=env)
    assert "Traceback" not in checked.stderr and runs(counter) == 0
    same = run_script("live_proxy", "--repo", repo, "--target", "uat", "--reference", "uat",
                      "--log", tmp_path / "l.jsonl", "--check", env=env)
    assert same.returncode == 1 and runs(counter) == 0
    for bad in ("mint.py", [], [sys.executable, 3], None):
        write_targets(targets, {"uat": {"url": "https://uat.example.com", "refresh": bad}})
        result = run_script("live_proxy", "--repo", repo, "--target", "uat", "--log",
                            tmp_path / "l.jsonl", "--check", env=env)
        assert result.returncode == 1 and result.stderr.startswith("error: uat: refresh"), bad
        assert "Traceback" not in result.stderr


def test_slow_refresh_command_is_stopped_with_its_child(tmp_path, monkeypatch):
    import live_proxy
    monkeypatch.setattr(live_proxy, "REFRESH_TIMEOUT", 1)
    marker = tmp_path / "child-alive"
    child = f"import time, pathlib; time.sleep(3); pathlib.Path({str(marker)!r}).write_text('x')"
    code = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); " \
           "time.sleep(60)"
    target = {"refresh": {"argv": [sys.executable, "-c", code], "dir": str(tmp_path),
                          "name": "uat", "repo": str(tmp_path / "repo")}}
    started = time.monotonic()
    try:
        live_proxy.mint(target)
    except live_proxy.BadTarget as exc:
        assert str(exc) == "uat: refresh command took longer than 1 s"
    else:
        raise AssertionError("mint returned")
    assert time.monotonic() - started < 10
    time.sleep(4)
    assert not marker.exists()  # the command's child was stopped with it


PARTIAL_MINT = """import json, pathlib
count = pathlib.Path("count.txt")
n = int(count.read_text()) + 1 if count.exists() else 1
count.write_text(str(n))
seats = {"bob": {"X-Seat": f"bob-Kq9{n}Zx"}}
if n == 1:
    seats["alice"] = {"X-Seat": "alice-Kq91Zx"}
print(json.dumps(seats))
"""


def test_account_left_out_of_a_later_mint_keeps_its_token(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [
        {"path": "/bob", "responses": [{"status": 401}, {}]},
        {"path": "/alice", "responses": [{}]}])
    targets.parent.mkdir(parents=True, exist_ok=True)
    (targets.parent / "mint.py").write_text(PARTIAL_MINT, encoding="utf-8")
    write_targets(targets, {"uat": {"url": stub_base, "refresh": [sys.executable, "mint.py"]}})
    proxy, base = start_proxy(repo, "uat", env, tmp_path / "proxy.jsonl", "--refresh-gap", "0")
    try:
        assert call(base + "/bob", headers={"X-Bug-Hunter-Account": "bob"})[0] == 200
        assert call(base + "/alice", headers={"X-Bug-Hunter-Account": "alice"})[0] == 200
    finally:
        stop(proxy, stub)
    assert sent_seats(stub_log) == ["bob-Kq91Zx", "bob-Kq92Zx", "alice-Kq91Zx"]
