import json
import stat
from pathlib import Path

from conftest import run_script

AWS = "AKIA" + "Q" * 16

GOOD = """# Any user can read any order by id

**Severity:** high
**Category:** authz
**CWE:** CWE-639
**Proof:** traced

## Where
- `src/routes/orders.js:12` (GET /orders/:id)
- `src/services/orders.js:30` (findById without owner filter)

## Evidence
```js
router.get("/orders/:id", auth, (req, res) => svc.findById(req.params.id))
```

## Impact
A logged-in user reads another customer's orders, including address and phone.

## Fix
Filter by `req.user.id` in `findById`, or check ownership in the route.
"""


def write(tmp_path, text, name="01.md"):
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))
    return path


def test_check_enforces_the_finding_format(tmp_path):
    assert run_script("findings", "check", write(tmp_path, GOOD)).returncode == 0
    assert run_script("findings", "check",
                      write(tmp_path, GOOD.replace("\n", "\r\n"), "crlf.md")).returncode == 0

    cases = {
        "severity": GOOD.replace("**Severity:** high", "**Severity:** urgent"),
        "category": GOOD.replace("**Category:** authz", "**Category:** misc"),
        "CWE": GOOD.replace("CWE-639", "639"),
        "proof": GOOD.replace("**Proof:** traced", "**Proof:** hunch"),
        "path:line": GOOD.replace("src/routes/orders.js:12", "src/routes/orders.js").replace(
            "src/services/orders.js:30", "the service"),
        "code block": GOOD.replace("```js\n", "").replace("```\n", ""),
        "Impact": GOOD.replace("## Impact\nA logged-in user reads another customer's orders, "
                               "including address and phone.\n", "## Impact\n"),
        "Fix": GOOD.split("## Fix")[0],
        "title": GOOD.replace("# Any user can read any order by id", "#"),
        "secret": GOOD.replace("## Fix\n", f"## Fix\nRotate `{AWS}`.\n"),
    }
    for word, text in cases.items():
        result = run_script("findings", "check", write(tmp_path, text, f"{word}.md"))
        assert result.returncode == 1, word
        assert word.lower() in result.stdout.lower(), (word, result.stdout)
        assert AWS not in result.stdout

    redacted = GOOD.replace("## Fix\n", "## Fix\n```\nAPI_KEY=<redacted>\n```\n")
    assert run_script("findings", "check", write(tmp_path, redacted, "r.md")).returncode == 0


def test_audit_folder_and_numbering(make_repo, fake_gh, tmp_path):
    env, _ = fake_gh
    repo = make_repo({"a.js": ""}, origin="git@github.com:acme/shop.git")
    result = run_script("findings", "dir", repo, env=env)
    assert result.returncode == 0, result.stderr
    audit = Path(result.stdout.strip())
    assert audit == Path(env["HOME"]) / ".bug-hunter/github.com/acme/shop/audit"
    assert audit.is_dir() and stat.S_IMODE(audit.stat().st_mode) == 0o700

    for name in ("01.md", "09.md", "REPORT.md", ".DS_Store"):
        (audit / name).write_text("x", encoding="utf-8")
    assert run_script("findings", "next", audit).stdout.strip() == "10"


def test_script_outputs_become_findings(tmp_path):
    out = tmp_path / "out dir"
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps([
        {"path": ".env", "line": 3, "pattern": "stripe-live-key", "length": 32,
         "committed": True, "severity": "critical"},
        {"path": "t/x.js", "line": 1, "pattern": "aws-access-key-id", "length": 20,
         "committed": True, "severity": "low"},
    ]), encoding="utf-8")
    assert run_script("findings", "from-secrets-scan", scan, out).returncode == 0

    npm7 = {"vulnerabilities": {
        "lodash": {"name": "lodash", "severity": "high", "range": "<4.17.21",
                   "via": [{"source": 1523, "title": "Prototype Pollution", "cwe": ["CWE-1321"],
                            "url": "https://github.com/advisories/GHSA-x", "range": "<4.17.21"}],
                   "fixAvailable": {"name": "lodash", "version": "4.17.21"}},
        "minimist": {"name": "minimist", "severity": "moderate", "range": "<1.2.6",
                     "via": ["mkdirp"], "fixAvailable": True},
    }}
    npm6 = {"advisories": {"118": {"id": 118, "module_name": "minimatch", "severity": "low",
                                   "title": "ReDoS", "cwe": "CWE-400",
                                   "vulnerable_versions": "<3.0.2",
                                   "patched_versions": ">=3.0.2", "url": "https://npmjs.com/118"}}}
    composer = {"advisories": {"guzzlehttp/psr7": [
        {"advisoryId": "PKSA-1", "packageName": "guzzlehttp/psr7", "title": "Header injection",
         "affectedVersions": "<1.8.4", "link": "https://x", "cve": "CVE-2022-24775"}]},
        "abandoned": {}}
    for kind, data in (("from-npm-audit", npm7), ("from-npm-audit", npm6),
                       ("from-composer-audit", composer)):
        path = tmp_path / f"{kind}-{len(json.dumps(data))}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = run_script("findings", kind, path, out)
        assert result.returncode == 0, result.stderr

    files = sorted(out.glob("*.md"))
    assert len(files) == 6
    texts = {f.name: f.read_text(encoding="utf-8") for f in files}
    for name, text in texts.items():
        assert run_script("findings", "check", out / name).returncode == 0, (name, text)
        assert stat.S_IMODE((out / name).stat().st_mode) == 0o600
    joined = "\n".join(texts.values())
    assert "**Severity:** critical" in joined and "**Category:** secrets" in joined
    assert "CWE-798" in joined and "CWE-1321" in joined and "CWE-400" in joined
    assert "CWE-1395" in joined and "4.17.21" in joined and "PKSA-1" in joined
    assert "**Severity:** medium" in joined and "**Proof:** advisory" in joined

    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    assert run_script("findings", "from-npm-audit", empty, out).returncode == 0
    assert len(list(out.glob("*.md"))) == 6
    for bad in ("{not json", "[]", '{"vulnerabilities": {"x": 5}}'):
        empty.write_text(bad, encoding="utf-8")
        result = run_script("findings", "from-npm-audit", empty, out)
        assert result.returncode == 1 and "Traceback" not in result.stderr, bad
        assert len(result.stderr.strip().splitlines()) == 1


def test_report_and_inventory(tmp_path):
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "01.md").write_text(GOOD.replace("**Severity:** high", "**Severity:** medium"),
                                 encoding="utf-8")
    (audit / "02.md").write_text(GOOD.replace("# Any user", "# Admin route open")
                                 .replace("**Severity:** high", "**Severity:** critical"),
                                 encoding="utf-8")
    (audit / "03.md").write_text("# broken\n", encoding="utf-8")
    blocks = tmp_path / "blocks.txt"
    blocks.write_text(
        "noise\n=== PII INVENTORY ===\n"
        "email | src/models/user.js:5 | src/log.js:9 | GET /me | mailchimp | yes (plain) | none\n"
        "phone | src/models/user.js:6 | - | GET /orders/:id | - | yes (plain) | none\n"
        "=== END ===\n=== PII INVENTORY ===\n"
        "email | src/models/user.js:5 | - | - | sentry (src/sentry.js:3) | - | -\n"
        "=== END ===\n", encoding="utf-8")
    assert run_script("findings", "inventory", blocks, audit).returncode == 0
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({
        "policy": False, "skipped_parts": ["lib (2 files)"], "not_audited": ["python"],
        "dropped": [{"title": "Open redirect", "reason": "NOT CONFIRMED — allowlist at x.js:4"}],
    }), encoding="utf-8")
    result = run_script("findings", "report", audit, "--meta", meta)
    assert result.returncode == 0, result.stderr
    report = (audit / "REPORT.md").read_text(encoding="utf-8")
    assert stat.S_IMODE((audit / "REPORT.md").stat().st_mode) == 0o600
    assert report.index("Admin route open") < report.index("Any user can read")
    assert "| 02 | critical |" in report and "traced" in report
    assert "critical: 1" in report and "medium: 1" in report and "authz: 2" in report
    assert "03.md" in report and "skipped" in report.lower()
    assert "mailchimp" in report and "sentry" in report and report.count("| email |") == 1
    assert "Open redirect" in report and "allowlist at x.js:4" in report
    assert "lib (2 files)" in report and "python" in report
    assert "no policy file" in report.lower()


def test_audit_findings_never_post_or_query_issues(tmp_path, fake_gh, make_repo):
    env, calls = fake_gh
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "01.md").write_text(GOOD, encoding="utf-8")
    result = run_script("post", drafts, "1", "--label", "bug", env=env)
    assert result.returncode == 1 and "audit finding" in result.stderr
    assert calls() == []

    repo = make_repo({"a.js": ""})
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "01.md").write_text(GOOD, encoding="utf-8")
    result = run_script("known", repo, audit, "--audit", env=env)
    assert result.returncode == 0, result.stderr
    assert "Any user can read any order by id" in result.stdout
    assert calls() == []
