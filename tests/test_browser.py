import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS, run_script
from test_live_proxy import (
    ORIGIN,
    call,
    entries,
    home_env,
    start_proxy,
    start_stub,
    stop,
    write_targets,
)
from test_reference import FAIL, PASS, routed

PACKAGE = json.dumps({"name": "shop", "private": True,
                      "devDependencies": {"@playwright/test": "1.60.0"}})
LOCK = json.dumps({"name": "shop", "lockfileVersion": 3, "packages": {
    "node_modules/@playwright/test": {"version": "1.60.0"}}})
ROUTES = {"server/app.py": '@app.post("/api/notes")\ndef add():\n    pass\n'}
UI = {"web/Notes.tsx": "export const Notes = () => <form><button>Save</button></form>;\n"}


def browsers(tmp_path: Path, build: str | None = "chromium-1223") -> dict:
    folder = tmp_path / "browsers dir"
    folder.mkdir(exist_ok=True)
    if build:
        (folder / build).mkdir(exist_ok=True)
    return {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(folder)}


def detect(repo, env):
    result = run_script("browser", "detect", repo, env=env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_detect_needs_the_package_the_lockfile_and_a_browser(make_repo, tmp_path):
    repo = make_repo({"web/package.json": PACKAGE, "web/package-lock.json": LOCK, **UI})
    found = detect(repo, browsers(tmp_path))
    assert (found["available"], found["dir"]) == (True, "web"), found

    no_browser = tmp_path / "empty"
    no_browser.mkdir()
    found = detect(repo, browsers(no_browser, None))
    assert found["available"] is False and "chromium" in found["reason"], found

    for files, word in (({"web/package.json": PACKAGE}, "lockfile"),
                        ({"web/package.json": json.dumps({"name": "shop"}),
                          "web/package-lock.json": LOCK}, "devDependencies")):
        bare = tmp_path / f"bare {word}"
        bare.mkdir()
        subprocess.run(["git", "init", "-q", str(bare)], check=True)
        for name, text in files.items():
            (bare / name).parent.mkdir(parents=True, exist_ok=True)
            (bare / name).write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(bare), "add", "-A"], check=True)
        found = detect(bare, browsers(tmp_path / f"bare {word}"))
        assert found["available"] is False and word in found["reason"], (word, found)


def scope(repo, env, *flags):
    result = run_script("scope", repo, "--live", *flags, env=env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_scope_keeps_ui_parts_when_the_browser_is_available(make_repo, tmp_path):
    repo = make_repo({"web/package.json": PACKAGE, "web/package-lock.json": LOCK, **ROUTES, **UI})
    out = scope(repo, browsers(tmp_path), "--browser")
    assert out["browser"]["available"] is True, out["browser"]
    ui = next(p for p in out["parts"] if p["dir"] == "web")
    assert "web-ui" in ui["edge_inputs"] and "live-http" in ui["edge_inputs"], ui

    missing = tmp_path / "none"
    missing.mkdir()
    out = scope(repo, browsers(missing, None), "--browser")
    assert out["browser"]["available"] is False and out["browser"]["reason"], out["browser"]
    assert [p["dir"] for p in out["parts"]] == ["server"], out["parts"]

    plain = scope(repo, browsers(tmp_path / "none"))
    assert "browser" not in plain and [p["dir"] for p in plain["parts"]] == ["server"]

    # Server-rendered templates make a route part a UI part too.
    (tmp_path / "t").mkdir()
    views = tmp_path / "t" / "repo"
    subprocess.run(["git", "init", "-q", str(views)], check=True)
    for name, text in {"package.json": PACKAGE, "package-lock.json": LOCK, **ROUTES,
                       "server/views/notes.ejs": "<form><button>Save</button></form>\n"}.items():
        (views / name).parent.mkdir(parents=True, exist_ok=True)
        (views / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(views), "add", "-A"], check=True)
    out = scope(views, browsers(tmp_path / "t"), "--browser")
    server = next(p for p in out["parts"] if p["dir"] == "server")
    assert "web-ui" in server["edge_inputs"], server

    # Playwright only in a test folder, which has no locked install: not available.
    tests_only = tmp_path / "t" / "tests only"
    subprocess.run(["git", "init", "-q", str(tests_only)], check=True)
    for name, text in {"tests/e2e/package.json": PACKAGE, "tests/e2e/package-lock.json": LOCK,
                       **ROUTES}.items():
        (tests_only / name).parent.mkdir(parents=True, exist_ok=True)
        (tests_only / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(tests_only), "add", "-A"], check=True)
    out = scope(tests_only, browsers(tmp_path / "t"), "--browser")
    assert out["browser"]["available"] is False and "install" in out["browser"]["reason"]


def test_the_fixture_app_is_hunted_in_the_browser(tmp_path):
    fixture = Path(__file__).resolve().parent / "fixtures" / "browser-app"
    repo = tmp_path / "browser app"
    shutil.copytree(fixture, repo, ignore=shutil.ignore_patterns("node_modules"))
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    (tmp_path / "b").mkdir()
    out = scope(repo, browsers(tmp_path / "b"), "--browser")
    assert out["browser"]["available"] is True, out["browser"]
    assert any("web-ui" in p["edge_inputs"] for p in out["parts"]), out["parts"]


def test_a_default_draft_heredoc_cannot_end_early():
    from drafts import problems

    early = ("# Double submit\n\n## What happens\nTwo notes.\n\n## Steps to reproduce\n```\n"
             "$ cat > bh-repro.spec.ts <<'BH_TEST_END'\ntest('x', () => {});\nBH_TEST_END\n"
             "rm -rf ~\nBH_TEST_END\n$ python3 browser.py run --test bh-repro.spec.ts\n"
             '{"result": "fail"}\n```\n\n## Expected\nOne.\n\n## Root cause\n`a.js`, `f`, 1.\n')
    assert any("BH_TEST_END" in p for p in problems(early)), problems(early)


def isolate_output(scratch: Path, env: dict, *flags) -> str:
    result = subprocess.run([sys.executable, "-I", str(SCRIPTS / "isolate.py"), str(scratch),
                             *flags], capture_output=True, text=True, encoding="utf-8", env=env)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_isolation_keeps_the_browsers_read_only(tmp_path):
    env = browsers(tmp_path)
    scratch = tmp_path / "scratch"
    shown = isolate_output(scratch, env, "--browser")
    assert f"PLAYWRIGHT_BROWSERS_PATH={env['PLAYWRIGHT_BROWSERS_PATH']}" in shown.replace(
        "'", ""), shown
    assert "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1" in shown
    # An explicit `playwright install` reads the download host: a dead one fails closed.
    assert "PLAYWRIGHT_DOWNLOAD_HOST=http://127.0.0.1:9" in shown
    assert "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD" not in isolate_output(scratch, env)


def raw_response(base: str, request: bytes) -> bytes:
    host, port = base.removeprefix("http://").split(":")
    with socket.create_connection((host, int(port)), timeout=5) as sock:
        sock.sendall(request)
        return sock.recv(4096)


def test_proxy_serves_absolute_form_only_for_itself(make_repo, tmp_path):
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, _ = home_env(tmp_path)
    stub, stub_base, stub_log = start_stub(tmp_path, [{"path": "/x", "responses": [{}]}])
    log = tmp_path / "proxy.jsonl"
    proxy, base = start_proxy(repo, stub_base, env, log)
    try:
        listener = base.removeprefix("http://")
        port = listener.split(":")[1]
        before = call(base + "/.bug-hunter/refusals")
        mine = raw_response(base, f"GET {base}/x HTTP/1.1\r\nHost: {listener}\r\n\r\n".encode())
        others = [raw_response(base, f"GET {url}/x HTTP/1.1\r\nHost: x\r\n\r\n".encode())
                  for url in ("http://127.0.0.1:9", f"http://localhost:{port}",
                              f"http://user@{listener}")]
        tunnel = raw_response(base, b"CONNECT example.com:443 HTTP/1.1\r\nHost: x\r\n\r\n")
        after = call(base + "/.bug-hunter/refusals")
    finally:
        stop(proxy, stub)
    assert b" 200 " in mine.split(b"\r\n")[0], mine[:80]
    assert [e["path"] for e in entries(stub_log)] == ["/x"]
    for refused, status in [*((o, b" 400 ") for o in others), (tunnel, b" 501 ")]:
        assert status in refused.split(b"\r\n")[0] and b"X-Bug-Hunter-Refused: 1" in refused
    assert {e["status"] for e in entries(log)} >= {400, 501}
    # The count browser.py reads to tell a refused run from a failed one.
    counts = [json.loads(body) for _, _, body in (before, after)]
    assert counts == [{"refused": 0}, {"refused": 4}], counts
    assert after[1].get("X-Bug-Hunter-Proxy") == "1"


def test_wrapper_config_pins_the_proxy_and_one_test():
    import browser

    text = browser.config_text("bh-repro.spec.ts", proxied=True)
    for wanted in ("process.env.ACCEPT_BASE_URL", "baseURL: base", "server: base",
                   "bypass: '<-loopback>'", "launchOptions: { proxy", "workers: 1",
                   "retries: 0", "browserName: 'chromium'", '"bh-repro.spec.ts"',
                   "testDir: 'bh-run'"):
        assert wanted in text, wanted
    assert "webServer" not in text and "playwright.config" not in text
    # Away from bug-hunter's proxy (a draft run on another machine) the base is the app itself.
    assert "proxy" not in browser.config_text("bh-repro.spec.ts", proxied=False)


FAKE_CLI = r"""
// A stand-in for @playwright/test's CLI: records how it was called, reports by the test text.
const fs = require('fs');
const http = require('http');
const config = fs.readFileSync('bh.playwright.config.mjs', 'utf8');
const dir = (config.match(/testDir: '([^']+)'/) || [null, '.'])[1];
fs.writeFileSync('called.json', JSON.stringify({argv: process.argv.slice(2),
  base: process.env.ACCEPT_BASE_URL, proxied: config.includes('proxy:')}));
const text = fs.readFileSync(dir + '/bh-repro.spec.ts', 'utf8');
function report(status, testStatus, message) {
  const result = message ? {status, error: {message}} : {status};
  fs.writeFileSync('bh-playwright-report.json', JSON.stringify({
    suites: [{specs: [{tests: [{status: testStatus, results: [result]}]}]}],
    stats: {expected: testStatus === 'expected' ? 1 : 0,
            unexpected: testStatus === 'unexpected' ? 1 : 0}}));
  process.exit(testStatus === 'expected' ? 0 : 1);
}
if (text.includes('SLEEP')) {
  setTimeout(() => {}, 120000);
} else if (text.includes('POST')) {
  // As a page would: a write the read-only target's proxy refuses, then a failed assertion.
  const req = http.request(process.env.ACCEPT_BASE_URL + '/orders', {method: 'POST'}, (res) => {
    res.resume();
    res.on('end', () => report('failed', 'unexpected', 'Error: toHaveCount failed'));
  });
  req.end('{}');
} else if (text.includes('LAUNCH')) {
  report('failed', 'unexpected', "browserType.launch: Executable doesn't exist at /x");
} else if (text.includes('XFAIL')) {
  report('failed', 'expected', 'Error: expected to fail');
} else if (text.includes('FAIL')) {
  report('failed', 'unexpected', '\u001b[31mError: expect(received).toBe(expected)\n\n' +
         'Expected: 1\nReceived: 2\n\n    at /x/bh-repro.spec.ts:3:5');
} else {
  report('passed', 'expected');
}
"""


def browser_run(copy, base, *args, env=None):
    ran = run_script("browser", "run", "--copy", copy, "--base", base, *args, env=env)
    assert ran.returncode == 0, ran.stderr
    return json.loads(ran.stdout)


def test_run_reports_pass_fail_and_not_run(make_repo, tmp_path):
    # Browser mode needs node, so this test does too.
    copy = tmp_path / "my cöpy"
    cli = copy / "node_modules" / "@playwright" / "test" / "cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text(FAKE_CLI, encoding="utf-8")
    # A repo test of the same name elsewhere in the copy is never run.
    (copy / "x").mkdir()
    (copy / "x" / "bh-repro.spec.ts").write_text("// FAIL", encoding="utf-8")
    nowhere = "http://127.0.0.1:5555"
    results = {}
    for name, body in (("pass", "test('ok', async () => {});"), ("fail", "// FAIL"),
                       ("xfail", "// XFAIL"), ("launch", "// LAUNCH")):
        (copy / "bh-repro.spec.ts").write_text(body, encoding="utf-8")
        results[name] = browser_run(copy, nowhere, "--test", "bh-repro.spec.ts")
    assert results["pass"] == {"result": "pass"}
    assert results["xfail"] == {"result": "pass"}, results["xfail"]
    assert results["fail"] == {"result": "fail", "step": 1, "message":
                               "Error: expect(received).toBe(expected)\nExpected: 1\nReceived: 2"}
    assert results["launch"]["result"].startswith("not run: "), results["launch"]
    called = json.loads((copy / "called.json").read_text(encoding="utf-8"))
    assert called == {"argv": ["test", "--config", "bh.playwright.config.mjs"],
                      "base": nowhere, "proxied": False}

    # Through bug-hunter's proxy: the browser is pinned to it, and a refusal is "not run".
    repo = make_repo({"a.py": ""}, origin=ORIGIN)
    env, targets = home_env(tmp_path)
    stub, stub_base, _ = start_stub(tmp_path, [{"path": "/orders", "responses": [{}]}])
    write_targets(targets, {"ro": {"url": stub_base}})
    proxy, base = start_proxy(repo, "ro", env, tmp_path / "p.jsonl")
    try:
        (copy / "bh-repro.spec.ts").write_text("// POST", encoding="utf-8")
        refused = browser_run(copy, base, "--test", "bh-repro.spec.ts")
        proxied = json.loads((copy / "called.json").read_text(encoding="utf-8"))["proxied"]
    finally:
        stop(proxy, stub)
    assert refused["result"].startswith("not run: the proxy refused"), refused
    assert proxied is True

    # A finding-v1 draft's test is written from its Repro JSON, never through a shell.
    draft = tmp_path / "d.md"
    draft.write_text("## repro (Finding-v1):\n~~~json\n"
                     + json.dumps({"runner": "playwright", "test": "// FAIL\n"}) + "\n~~~\n",
                     encoding="utf-8")
    assert browser_run(copy, nowhere, "--draft", draft)["result"] == "fail"
    assert (copy / "bh-repro.spec.ts").read_text(encoding="utf-8") == "// FAIL\n"

    # The locked version needs a chromium build that isn't installed: never downloaded.
    core = copy / "node_modules" / "playwright-core"
    core.mkdir()
    (core / "browsers.json").write_text(json.dumps({"browsers": [
        {"name": "chromium-headless-shell", "revision": "9999"}]}), encoding="utf-8")
    missing = browser_run(copy, nowhere, "--test", "bh-repro.spec.ts", env=browsers(tmp_path))
    assert missing["result"].startswith("not run: ") and "9999" in missing["result"], missing
    (core / "browsers.json").unlink()

    # A test that hangs is stopped, its whole process tree with it.
    (copy / "bh-repro.spec.ts").write_text("// SLEEP", encoding="utf-8")
    hung = browser_run(copy, nowhere, "--test", "bh-repro.spec.ts",
                       env={**os.environ, "BH_BROWSER_TIMEOUT": "2"})
    assert hung["result"].startswith("not run: ") and "2 seconds" in hung["result"], hung

    (copy / "node_modules").rename(copy / "gone")
    assert browser_run(copy, nowhere, "--test", "bh-repro.spec.ts")["result"].startswith(
        "not run: ")


TEST_SOURCE = ("import { test, expect } from '@playwright/test';\n"
               "test('one note per save', async ({ page }) => {\n"
               "  const [name, value] = process.env.ACCEPT_ACCOUNT_BOB.split(': ');\n"
               "  await page.setExtraHTTPHeaders({ [name]: value });\n"
               "  await page.goto('/');\n"
               "  await page.dblclick('button');\n"
               "  await expect(page.locator('li')).toHaveCount(1);\n"
               "});\n")


def playwright_draft(observed):
    return ("# Double submit saves two notes\nSet before running: `BASE`, `ACCEPT_ACCOUNT_BOB`\n"
            "Severity: high\n\n## What happens\nA double click saves two notes.\n\n"
            "## Steps to reproduce\nRendered from the Repro section.\n\n"
            "## Repro (finding-v1)\n```json\n"
            + json.dumps({"runner": "playwright", "test": TEST_SOURCE}) + "\n```\n\n"
            "## Observed (finding-v1)\n```json\n" + json.dumps(observed) + "\n```\n\n"
            "## Expected\nOne note per save.\n\n## Root cause\n`web/app.js`, `save`, line 4: "
            "the button stays enabled.\n")


def test_playwright_repro_becomes_a_finding(make_repo, tmp_path):
    repo = make_repo({"a.py": ""})
    out = tmp_path / "out"
    draft = tmp_path / "d.md"
    draft.write_text(playwright_draft({"rebuild": FAIL}), encoding="utf-8")
    rendered = run_script("finding_v1", "render", "--draft", draft)
    assert rendered.returncode == 0, rendered.stderr
    steps = draft.read_text(encoding="utf-8").split("## Steps to reproduce")[1]
    assert "await page.dblclick('button');" in steps
    assert 'python3 browser.py run --test bh-repro.spec.ts --base "$BASE"' in steps
    wrote = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft)
    assert wrote.returncode == 0, wrote.stderr
    finding = json.loads((out / "BH-0001.json").read_text(encoding="utf-8"))
    assert finding["repro"] == {"runner": "playwright", "test": TEST_SOURCE,
                                "env": ["ACCEPT_BASE_URL", "ACCEPT_ACCOUNT_BOB"]}
    assert routed(out / "BH-0001.json")[0] == 0

    draft.write_text(playwright_draft({"rebuild": FAIL, "reference": PASS}), encoding="utf-8")
    r1, r2 = tmp_path / "r1.json", tmp_path / "r2.json"
    r1.write_text(json.dumps(FAIL), encoding="utf-8")
    r2.write_text(json.dumps(PASS), encoding="utf-8")
    wrote = run_script("finding_v1", "write", "--repo", repo, "--out", out, "--draft", draft,
                       "--rebuild", r1, "--reference", r2)
    assert wrote.returncode == 0, wrote.stderr
    finding = json.loads((out / "BH-0002.json").read_text(encoding="utf-8"))
    assert (finding["class"], finding["repro"]["runner"]) == ("build-defect", "playwright")
