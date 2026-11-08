"""Tell whether a repo can hunt in a browser, and run one Playwright repro through the proxy.

Standard library only and standalone: a draft fetches this file at a pinned version, so a
repro runs from the draft alone on another machine.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

PACKAGE = "@playwright/test"
LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb")
CONFIG = "bh.playwright.config.mjs"
DRAFT_TEST = "bh-repro.spec.ts"
RUN_DIR = "bh-run"  # the only folder the run's config looks in for tests
REPORT = "bh-playwright-report.json"
CLI = Path("node_modules") / "@playwright" / "test" / "cli.js"
BROWSERS_JSON = Path("node_modules") / "playwright-core" / "browsers.json"
REFUSALS = "/.bug-hunter/refusals"  # live_proxy.py's count of the requests it refused
TIMEOUT = 300
MAX_MESSAGE = 500
MAX_LINES = 6
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
TEST_NAME = re.compile(r"[A-Za-z0-9_.-]+\.(?:spec|test)\.(?:ts|js|mjs)")
# Failures of the run itself, not of the app: no browser, no network, out of time.
NOT_THE_APP = re.compile(r"browserType\.launch|Executable doesn't exist|net::ERR_|"
                         r"Target page, context or browser has been closed|Test timeout of")


def browsers_dir(env: dict[str, str]) -> Path:
    """Where Playwright keeps its browsers, as Playwright itself looks for them."""
    chosen = env.get("PLAYWRIGHT_BROWSERS_PATH")
    if chosen and chosen != "0":
        return Path(chosen)
    if sys.platform == "win32":
        return Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ms-playwright"


def _tracked(repo: str) -> list[str] | None:
    try:
        out = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", "ls-files", "-z"],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [name.decode("utf-8", "replace") for name in out.split(b"\0") if name]


def _has_dev_dependency(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    deps = data.get("devDependencies") if isinstance(data, dict) else None
    return isinstance(deps, dict) and PACKAGE in deps


def detect(repo: str, env: dict[str, str]) -> dict:
    """{available, reason, dir}: a locked @playwright/test dev dependency and a chromium build."""
    tracked = _tracked(repo)
    if tracked is None:
        return {"available": False, "reason": f"{repo} is not a git repo", "dir": None}
    names = set(tracked)
    root = Path(repo)
    listing = [n for n in tracked if PurePosixPath(n).name == "package.json"
               and "node_modules" not in PurePosixPath(n).parts]
    wanting = [n for n in sorted(listing) if not (root / n).is_symlink()
               and _has_dev_dependency(root / n)]
    if not wanting:
        return {"available": False, "dir": None,
                "reason": f"no package.json lists {PACKAGE} in devDependencies"}
    locked = None
    for name in wanting:
        folder = PurePosixPath(name).parent
        for lock in LOCKFILES:
            path = (folder / lock).as_posix()
            if path in names and not (root / path).is_symlink():
                try:
                    # Bytes: bun.lockb is binary, and the name is still spelled out in it.
                    found = PACKAGE.encode() in (root / path).read_bytes()
                except OSError:
                    continue
                if found:
                    locked = folder.as_posix()
                    break
        if locked is not None:
            break
    if locked is None:
        return {"available": False, "dir": None,
                "reason": f"no tracked lockfile beside {wanting[0]} holds {PACKAGE}, so the "
                          "copy can't install it from the lockfile"}
    where = browsers_dir(env)
    try:
        builds = [p.name for p in where.iterdir() if p.is_dir()
                  and re.fullmatch(r"chromium(?:_headless_shell)?-\d+", p.name)]
    except OSError:
        builds = []
    if not builds:
        return {"available": False, "dir": locked,
                "reason": f"no chromium build in {where}: browser mode uses only browsers "
                          "already installed, and never downloads one"}
    return {"available": True, "reason": "", "dir": locked}


def config_text(test: str, proxied: bool) -> str:
    """A Playwright config for one repro: chromium only, one test, and (`proxied`) the proxy."""
    # The repo's own config isn't used: it can start a webServer or a globalSetup, or name
    # browsers that aren't installed, none of which may run against a live target.
    proxy = ("    // Every request, loopback too, goes through bug-hunter's proxy listener.\n"
             "    proxy: { server: base, bypass: '<-loopback>' },\n"
             "    // Also any browser the test launches itself, and its own traffic.\n"
             "    launchOptions: { proxy: { server: base, bypass: '<-loopback>' } },\n"
             if proxied else "")
    return f"""// Written by bug-hunter's browser.py for one repro.
import {{ defineConfig }} from '{PACKAGE}';

const base = process.env.ACCEPT_BASE_URL;

export default defineConfig({{
  testDir: '{RUN_DIR}',
  testMatch: [{json.dumps(test)}],
  workers: 1,
  retries: 0,
  fullyParallel: false,
  reporter: [['json', {{ outputFile: '{REPORT}' }}]],
  use: {{
    baseURL: base,
{proxy}    trace: 'off',
    video: 'off',
    screenshot: 'off',
  }},
  projects: [{{ name: 'chromium', use: {{ browserName: 'chromium' }} }}],
}});
"""


def _message(text: str) -> str:
    # Enough of the error (its Expected and Received lines) that two different wrong
    # behaviours don't read the same; never the stack.
    lines = [line.strip() for line in ANSI.sub("", text).split("\n")]
    kept = [line for line in lines if line and not line.startswith("at ")][:MAX_LINES]
    return "\n".join(kept)[:MAX_MESSAGE]


def _first_failure(suites: list) -> str | None:
    for suite in suites or []:
        if not isinstance(suite, dict):
            continue
        for spec in suite.get("specs") or []:
            for test in (spec.get("tests") or []) if isinstance(spec, dict) else []:
                if not isinstance(test, dict):
                    continue
                # The test's own verdict: a test.fail() that fails as meant is a pass.
                if test.get("status") in ("expected", "skipped"):
                    continue
                for result in test.get("results") or []:
                    if isinstance(result, dict) and result.get("status") not in (
                            "passed", "skipped"):
                        error = result.get("error") or {}
                        return _message(str(error.get("message") or result.get("status")))
        found = _first_failure(suite.get("suites"))
        if found:
            return found
    return None


def test_from_draft(draft: Path) -> str | None:
    """The test source in a finding-v1 draft's `## Repro (finding-v1)` JSON, or None."""
    # Read as data, so an agent never writes a hunter's test through a shell.
    try:
        text = draft.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    section = re.search(r"^##[ \t]+repro \(finding-v1\)[ \t]*:?[ \t]*\n(.*?)(?=^## |\Z)",
                        text, re.M | re.S | re.I)
    block = re.search(r"^(`{3,}|~{3,})[^\n]*\n(.*?)^\1[ \t]*$", section[1], re.M | re.S) \
        if section else None
    try:
        repro = json.loads(block[2]) if block else None
    except ValueError:
        return None
    if isinstance(repro, dict) and repro.get("runner") == "playwright" \
            and isinstance(repro.get("test"), str) and repro["test"].strip():
        return repro["test"]
    return None


def _refusals(base: str) -> int | None:
    """The proxy's count of refused requests, or None when `base` isn't bug-hunter's proxy."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(base.rstrip("/") + REFUSALS, timeout=5) as response:
            if response.headers.get("X-Bug-Hunter-Proxy") != "1":
                return None
            count = json.loads(response.read(1000).decode("utf-8")).get("refused")
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return None
    return count if isinstance(count, int) and not isinstance(count, bool) else None


def _missing_browser(copy: Path, env: dict[str, str]) -> str | None:
    """The chromium build the copy's locked Playwright needs, when it isn't installed."""
    try:
        listed = json.loads((copy / BROWSERS_JSON).read_text(encoding="utf-8"))["browsers"]
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
        return None  # an unknown layout: the launch itself will say
    wanted = [b for b in listed if isinstance(b, dict) and b.get("name") in (
        "chromium", "chromium-headless-shell") and isinstance(b.get("revision"), str)]
    where = browsers_dir(env)
    folders = {f"{b['name'].replace('-headless-shell', '_headless_shell')}-{b['revision']}"
               for b in wanted}
    if not folders or any((where / f).is_dir() for f in folders):
        return None
    return wanted[0]["revision"]


def _node() -> str | None:
    # Windows looks in the current folder first, which is the hunted repo's copy.
    os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
    return shutil.which("node")


def _stop_tree(process: subprocess.Popen) -> None:
    # The runner's browser and workers outlive a plain kill and would keep using the proxy.
    if sys.platform == "win32":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        subprocess.run([str(taskkill), "/T", "/F", "/PID", str(process.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass  # already gone
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _timeout() -> int:
    try:
        return max(1, min(int(os.environ.get("BH_BROWSER_TIMEOUT", TIMEOUT)), 3600))
    except ValueError:
        return TIMEOUT


def run(copy: Path, test: str, base: str) -> dict:
    """Run one test file in `copy` against `base`, as replay's {"result": …}."""
    if not TEST_NAME.fullmatch(test):
        return {"result": "not run: --test must be a file name like bh-repro.spec.ts"}
    if not (copy / test).is_file():
        return {"result": f"not run: no {test} in the copy"}
    if not (copy / CLI).is_file():
        return {"result": f"not run: no {CLI.as_posix()} in the copy; run the locked install "
                          "first"}
    revision = _missing_browser(copy, dict(os.environ))
    if revision is not None:
        return {"result": f"not run: the locked Playwright needs chromium {revision}, which "
                          "isn't installed; browser mode never downloads one"}
    node = _node()
    if node is None:
        return {"result": "not run: node is not installed"}
    before = _refusals(base)
    limit = _timeout()
    report = copy / REPORT
    try:
        report.unlink(missing_ok=True)
        (copy / RUN_DIR).mkdir(exist_ok=True)
        shutil.copyfile(copy / test, copy / RUN_DIR / test)
        (copy / CONFIG).write_text(config_text(test, before is not None), encoding="utf-8")
        process = subprocess.Popen(
            [node, str(CLI), "test", "--config", CONFIG], cwd=copy,
            env={**os.environ, "ACCEPT_BASE_URL": base}, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=sys.platform != "win32",
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    except OSError as exc:
        return {"result": f"not run: {type(exc).__name__}"}
    try:
        exit_code = process.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        _stop_tree(process)
        return {"result": f"not run: the test ran past {limit} seconds"}
    after = _refusals(base) if before is not None else None
    if before is not None and (after is None or after > before):
        return {"result": "not run: the proxy refused a request during this run (budget, "
                          "writes or another origin), so the result says nothing about the app"}
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return {"result": f"not run: playwright wrote no report (exit {exit_code})"}
    failure = _first_failure(data.get("suites") if isinstance(data, dict) else None)
    if failure and NOT_THE_APP.search(failure):
        return {"result": f"not run: {failure.split(chr(10))[0]}"}
    if failure:
        return {"result": "fail", "step": 1, "message": failure}
    stats = data.get("stats") if isinstance(data, dict) else None
    if not isinstance(stats, dict) or not stats.get("expected"):
        return {"result": "not run: no test ran"}
    return {"result": "pass"}


def _main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("detect", help="can this repo hunt in a browser, and if not, why")
    d.add_argument("repo")
    r = sub.add_parser("run", help="run one Playwright test file through the proxy")
    given = r.add_mutually_exclusive_group(required=True)
    given.add_argument("--test", help="the test file, in the copy's root")
    given.add_argument("--draft", type=Path,
                       help=f"a finding-v1 draft: its test is written to {DRAFT_TEST} first")
    r.add_argument("--base", required=True, help="the proxy listener: $BASE or $REF_BASE")
    r.add_argument("--copy", default=".", type=Path,
                   help="the folder holding the locked install (default: here)")
    args = parser.parse_args(argv)
    if args.command == "detect":
        out = detect(args.repo, dict(os.environ))
    elif args.draft is not None:
        source = test_from_draft(args.draft)
        if source is None:
            out = {"result": "not run: the draft has no playwright Repro (finding-v1) JSON"}
        else:
            try:
                (args.copy / DRAFT_TEST).write_text(source, encoding="utf-8", newline="")
                out = run(args.copy, DRAFT_TEST, args.base)
            except OSError as exc:
                out = {"result": f"not run: can't write {DRAFT_TEST} ({type(exc).__name__})"}
    else:
        out = run(args.copy, args.test, args.base)
    # ASCII: a target's text must not reach a terminal as control characters.
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
