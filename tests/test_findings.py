import json
import os
import re
from pathlib import Path

import pytest
from conftest import mode_is, run_script

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

    code = GOOD.replace("## Fix\n", '## Fix\n```py\npassword = request.form["password"]\n'
                        "token = jwt.sign(payload)\n```\n")
    assert run_script("findings", "check", write(tmp_path, code, "code.md")).returncode == 0

    for partial in ("postgres://app:Pr0dPa55<redacted>@db", "sk-" + "proj-" + "Ab12" + "XXXX"):
        text = GOOD.replace("## Fix\n", f"## Fix\n```\n{partial}\n```\n")
        result = run_script("findings", "check", write(tmp_path, text, "partial.md"))
        assert result.returncode == 1 and "secret" in result.stdout, partial


def test_check_keeps_sections_after_a_traceback_caret_line(tmp_path):
    caret = 'router.get("/orders/:id", auth, (req, res) => svc.findById(req.params.id))\n'
    text = GOOD.replace(caret, caret + "    ~~~~^^^^\n")
    assert run_script("findings", "check", write(tmp_path, text)).returncode == 0


def test_check_with_repo_needs_where_lines_that_exist(tmp_path):
    # node-express-realworld-example-app (B0 run 5): one finding cited absolute paths, so dedupe
    # missed its twin; another cited src/main.ts:85 in a 57-line file.
    repo = tmp_path / "my repo"
    for name in ("src/routes/orders.js", "src/services/orders.js"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text("x\n" * 40, encoding="utf-8")
    absolute = GOOD.replace("`src/routes/orders.js:12`",
                            f"`{(repo / 'src/routes/orders.js').as_posix()}:12`")
    for text in (GOOD, absolute):
        result = run_script("findings", "check", write(tmp_path, text), "--repo", repo)
        assert result.returncode == 0, result.stdout

    cases = {
        "past the end": GOOD.replace("orders.js:30", "orders.js:85"),
        "no such file": GOOD.replace("src/routes/orders.js:12", "src/routes/order.js:12"),
        "outside": GOOD.replace("src/routes/orders.js:12", "../outside.js:1"),
    }
    for word, text in cases.items():
        result = run_script("findings", "check", write(tmp_path, text, "bad.md"), "--repo", repo)
        assert result.returncode == 1 and word in result.stdout, (word, result.stdout)


def test_citations_outside_the_repo_are_never_opened_or_echoed(tmp_path, monkeypatch):
    # resolve() on `\\host\share\x` makes Windows connect to that host with the owner's
    # credentials, and a citation can be a secret the auditor quoted, so it is never echoed.
    import findings

    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src/a.js").write_text("x\n", encoding="utf-8")
    resolved = []
    real_resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve",
                        lambda self, *a, **k: resolved.append(str(self)) or real_resolve(self))
    text = GOOD.replace(
        "- `src/services/orders.js:30` (findById without owner filter)",
        "- `\\\\attacker\\share\\x.ts:1`\n- `//attacker/share/y.ts:2`\n"
        "- `DB_URL=postgres://admin:hunter2@db:5432`")
    problems = findings._citation_problems(text, repo)
    assert not any("attacker" in path for path in resolved)
    assert sum("outside the repo" in p for p in problems) >= 2
    assert not any("hunter2" in p or "attacker" in p for p in problems)


def test_dedupe_with_repo_matches_absolute_and_relative_citations(tmp_path):
    repo, new, audit = tmp_path / "my repo", tmp_path / "new", tmp_path / "audit"
    new.mkdir()
    audit.mkdir()
    absolute = GOOD.replace("`src/services/orders.js:30`",
                            f"`{(repo / 'src/services/orders.js').as_posix()}:30`")
    (new / "a.md").write_text(GOOD, encoding="utf-8")
    (new / "b.md").write_text(absolute, encoding="utf-8")
    assert run_script("findings", "dedupe", new, audit, "--repo", repo).returncode == 0
    assert len(list(new.glob("*.md"))) == 1


def test_audit_folder_and_numbering(make_repo, fake_gh, tmp_path):
    env, _ = fake_gh
    repo = make_repo({"a.js": ""}, origin="git@github.com:acme/shop.git")
    result = run_script("findings", "dir", repo, env=env)
    assert result.returncode == 0, result.stderr
    audit = Path(result.stdout.strip())
    assert audit == Path(env["HOME"]) / ".bug-hunter/github.com/acme/shop/audit"
    assert audit.is_dir() and mode_is(audit, 0o700)

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
        assert mode_is(out / name, 0o600)
    joined = "\n".join(texts.values())
    assert "**Severity:** critical" in joined and "**Category:** secrets" in joined
    assert "CWE-798" in joined and "CWE-1321" in joined and "CWE-400" in joined
    assert "CWE-1395" in joined and "4.17.21" in joined and "PKSA-1" in joined
    assert "**Severity:** medium" in joined and "**Proof:** advisory" in joined

    clean = tmp_path / "clean.json"
    clean.write_text('{"auditReportVersion": 2, "vulnerabilities": {}, "metadata": {}}', "utf-8")
    assert run_script("findings", "from-npm-audit", clean, out).returncode == 0
    clean.write_text('{"advisories": [], "abandoned": []}', "utf-8")
    assert run_script("findings", "from-composer-audit", clean, out).returncode == 0
    assert len(list(out.glob("*.md"))) == 6
    empty = tmp_path / "empty.json"
    for bad in ("{not json", "[]", '{"vulnerabilities": {"x": 5}}', "{}",
                '{"error": {"code": "ENOTFOUND", "summary": "request to registry failed"}}'):
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
        "field | defined (path:line) | logged | returned | sent to | stored | deletion\n"
        "email | src/models/user.js:5 | src/log.js:9 | GET /me | mailchimp | yes (plain) | none\n"
        "phone | src/models/user.js:6 | - | GET /orders/:id | - | yes (plain) | none\n"
        "=== END ===\n=== PII INVENTORY ===\n"
        "| email | src/models/user.js:5 | - | - | sentry (src/sentry.js:3) | - | - |\n"
        f"token | src/x.js:1 | {AWS} | - | - | - | -\n"
        "=== END ===\n", encoding="utf-8")
    assert run_script("findings", "inventory", blocks, audit).returncode == 0
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({
        "policy": False, "secrets_scanned": True, "audited": [], "audit_failures": [],
        "check_failed": [
            {"file": "agent-2.md", "problems": ["NOT CONFIRMED — allowlist at x.js:4"]},
            {"file": "agent-3.md", "problems": [f"Key {AWS} in config"]}],
    }), encoding="utf-8")
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps({
        "parts": [{"id": 1, "dir": "src", "files": ["src/a.py"], "stacks": ["python"],
                   "checklists": ["generic", "pii"], "no_checklist": ["python"]}],
        "skipped": [{"id": 2, "dir": "lib", "files": ["lib/a.js", "lib/b.js"]}],
        "audits": [], "coverage": {}}), encoding="utf-8")
    result = run_script("findings", "report", audit, "--meta", meta, "--scope", scope)
    assert result.returncode == 0, result.stderr
    report = (audit / "REPORT.md").read_text(encoding="utf-8")
    assert mode_is(audit / "REPORT.md", 0o600)
    assert report.index("Admin route open") < report.index("Any user can read")
    assert "| 02 | critical |" in report and "traced" in report
    assert "critical: 1" in report and "medium: 1" in report and "authz: 2" in report
    assert "03.md" in report and "skipped" in report.lower()
    assert "mailchimp" in report and "sentry" in report and report.count("| email |") == 1
    assert "agent-2.md" in report and "allowlist at x.js:4" in report
    assert "lib (2 files)" in report and "python" in report
    assert "no policy file" in report.lower()
    assert AWS not in report and "withheld" in report
    assert "| field |" in report and report.count("| field |") == 1
    assert "| defined (path:line) |" not in report

    bad_meta = tmp_path / "bad.json"
    bad_meta.write_text(json.dumps({"check_failed": ["just a string", 5]}), encoding="utf-8")
    result = run_script("findings", "report", audit, "--meta", bad_meta)
    assert result.returncode == 1 and "Traceback" not in result.stderr

    blocks.write_text("=== PII INVENTORY ===\nphone2 | a.js:1 | - | - | - | - | -\n"
                      "=== END ===\n", encoding="utf-8")
    assert run_script("findings", "inventory", blocks, audit).returncode == 0
    merged = (audit / "inventory.md").read_text(encoding="utf-8")
    assert "| email |" in merged and "| phone2 |" in merged


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


def test_npm_fix_names_the_right_package_and_reruns_dedupe(tmp_path):
    out = tmp_path / "new"
    data = {"auditReportVersion": 2, "vulnerabilities": {
        "minimist": {"name": "minimist", "severity": "moderate", "range": "<1.2.6",
                     "via": [{"title": "Prototype Pollution", "cwe": ["CWE-1321"],
                              "url": "https://x"}],
                     "fixAvailable": {"name": "mkdirp", "version": "0.5.6",
                                      "isSemVerMajor": False}}}}
    path = tmp_path / "npm.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert run_script("findings", "from-npm-audit", path, out).returncode == 0
    [finding] = out.glob("*.md")
    text = finding.read_text(encoding="utf-8")
    assert "upgrade mkdirp to 0.5.6" in text.lower() and "minimist" in text

    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "01.md").write_text(text, encoding="utf-8")
    assert run_script("findings", "from-npm-audit", path, out).returncode == 0
    (out / "agent-1.md").write_text(GOOD, encoding="utf-8")
    (out / "agent-2.md").write_text(GOOD.replace("**Severity:** high", "**Severity:** critical"),
                                    encoding="utf-8")
    result = run_script("findings", "dedupe", out, audit)
    assert result.returncode == 0, result.stderr
    left = sorted(p.name for p in out.glob("*.md"))
    assert left == ["agent-2.md"]


def test_known_secrets_are_withheld_and_code_is_not(make_repo, tmp_path):
    letters = "letmein" + "nowplease"
    jwt = "eyJ" + "hbGciOiJIUzI1" + ".eyJ" + "zdWIiOiIxMjM0" + ".Sf1KxwRJ" + "SMeKKF2QT4"
    dotted = "abc" + ".def" + ".Gh1jk2Lm"
    json_key = "Zq9" + "TxW2vLp8Rk"
    short = "Hu" + "n7er"
    repo = make_repo({
        ".env": f"DB_PASSWORD={letters}\nAUTH_TOKEN={jwt}\nJWT_SECRET={dotted}\n"
                f"PIN_PASSWORD={short}\n",
        "config/app.json": f'{{"api_key": "{json_key}"}}\n',
    })
    prints = tmp_path / "fingerprints.json"
    scan = run_script("secrets_scan", repo, "--fingerprints", prints)
    assert scan.returncode == 0, scan.stderr
    raw = prints.read_text(encoding="utf-8")
    for value in (letters, jwt, dotted, json_key, short):
        assert value not in raw and value[:8] not in raw
    assert mode_is(prints, 0o600)

    leaks = (f"DB_PASSWORD={letters}", f"- reason: config has {letters}",
             f'"api_key": "{json_key}"',
             f"X-API-Key: {json_key}", f"Authorization: Bearer {jwt}", f"AUTH={jwt[:12]}",
             f"| cell | {dotted} |", f"masked {json_key[:8]}xxxx", f"pin={short}",
             "AKIA" + "ABCD" + "X" * 12)
    for leak in leaks:
        text = GOOD.replace("## Fix\n", f"## Fix\n```\n{leak}\n```\n")
        result = run_script("findings", "check", write(tmp_path, text, "leak.md"),
                            "--fingerprints", prints)
        assert result.returncode == 1 and "secret" in result.stdout, leak

    code = ['password := r.FormValue("password")', "if (password === input) {",
            "tokens.map(token => token.trim())", "(token := get())", "key_size=1024",
            "max_tokens=4096", "{ key: 1 }", "the CSRF token: per-session",
            'password = request.form["password"]', "set `API_KEY=` in the env",
            "sha256: " + "ab12" * 16, "Password must be rotated"]
    text = GOOD.replace("## Fix\n", "## Fix\n```\n" + "\n".join(code) + "\n```\n")
    result = run_script("findings", "check", write(tmp_path, text, "code.md"),
                        "--fingerprints", prints)
    assert result.returncode == 0, result.stdout

    audit = tmp_path / "audit"
    audit.mkdir()
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"dropped": [
        {"title": "x", "reason": f"NOT CONFIRMED — .env has DB_PASSWORD={letters}"},
        {"title": f"token {jwt}", "reason": "failed check"}]}), encoding="utf-8")
    blocks = tmp_path / "blocks.txt"
    blocks.write_text(f"=== PII INVENTORY ===\nemail | a.js:1 | {json_key} | - | - | - | -\n"
                      "=== END ===\n", encoding="utf-8")
    assert run_script("findings", "inventory", blocks, audit,
                      "--fingerprints", prints).returncode == 0
    assert run_script("findings", "report", audit, "--meta", meta,
                      "--fingerprints", prints).returncode == 0
    report = (audit / "REPORT.md").read_text(encoding="utf-8")
    for value in (letters, jwt, json_key):
        assert value not in report and value[:8] not in report


def test_dedupe_keys_on_path_line_and_merges_where(tmp_path):
    new, audit = tmp_path / "new", tmp_path / "audit"
    new.mkdir()
    audit.mkdir()
    first = GOOD.replace("- `src/services/orders.js:30` (findById without owner filter)",
                         "- `src/services/orders.js:30` (no owner filter) (Fix here)")
    second = (GOOD.replace("**Severity:** high", "**Severity:** critical")
              .replace("# Any user can read any order by id", "# Orders readable by anyone")
              .replace("- `src/routes/orders.js:12` (GET /orders/:id)",
                       "- `src/routes/admin.js:40` (GET /admin/orders/:id)")
              .replace("- `src/services/orders.js:30` (findById without owner filter)",
                       "- `src/services/orders.js:30` missing ownership check (fix here)"))
    (new / "a.md").write_text(first, encoding="utf-8")
    (new / "b.md").write_text(second, encoding="utf-8")
    assert run_script("findings", "dedupe", new, audit).returncode == 0
    [kept] = list(new.glob("*.md"))
    text = kept.read_text(encoding="utf-8")
    assert "**Severity:** critical" in text
    assert "src/routes/orders.js:12" in text and "src/routes/admin.js:40" in text
    assert run_script("findings", "check", kept).returncode == 0

    result = run_script("findings", "dedupe", audit, audit)
    assert result.returncode == 1 and "same folder" in result.stderr


def test_known_values_are_found_whatever_surrounds_them(make_repo, tmp_path):
    letters = "letmein" + "nowplease"
    short = "Hu" + "n7er"
    body = ["MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7" + "Vq" * 6,
            "kU2Zq9TxW2vLp8Rk" + "Ab" * 22]
    repo = make_repo({
        ".env": f"DB_PASSWORD={letters}\nPIN_PASSWORD={short}\nTOKEN_TTL=3600\nKEY_ID=1\n"
                "SESSION_SECRET_ROTATE=true\nAPI_KEY_HEADER=x-api-key\n",
        "deploy/key.pem": "-----BEGIN " + "PRIVATE KEY-----\n" + "\n".join(body)
                          + "\n-----END " + "PRIVATE KEY-----\n",
        "db.yaml": "url: postgres://postgres:postgres@db:5432/app\n",
    })
    prints = tmp_path / "fingerprints.json"
    assert run_script("secrets_scan", repo, "--fingerprints", prints).returncode == 0

    leaks = (f"the .env password is {letters}.", f"**{letters}**", f"{letters}!",
             f"/{letters}/", f"{letters[:12]}…", f"{short}.", f"`{short}`", body[0], body[1][:40])
    for leak in leaks:
        text = GOOD.replace("## Fix\n", f"## Fix\n```\n{leak}\n```\n")
        result = run_script("findings", "check", write(tmp_path, text, "leak.md"),
                            "--fingerprints", prints)
        assert result.returncode == 1 and "secret" in result.stdout, leak

    harmless = GOOD.replace("src/routes/orders.js:12", "src/routes/orders.js:1").replace(
        "## Fix\n", "## Fix\nSet TOKEN_TTL to 3600, send the `x-api-key` header, "
        "true for postgres, line 8.\n```\nsha256 " + "ab12" * 16 + "\n```\n")
    result = run_script("findings", "check", write(tmp_path, harmless, "ok.md"),
                        "--fingerprints", prints)
    assert result.returncode == 0, result.stdout


def test_doc_placeholders_and_cut_keys(tmp_path):
    ok = GOOD.replace("## Fix\n", "## Fix\nUse a key like `sk-proj-...` or `sk-ant-…`, "
                      'and cache as `cacheKey: "users:v2"`.\n')
    assert run_script("findings", "check", write(tmp_path, ok, "ok.md")).returncode == 0
    for cut in ("AKIA" + "Q3J5ZP", "sk-" + "proj-" + "Ab12Cd<redacted>",
                "ghp" + "_" + "Ab12Cd (truncated)"):
        text = GOOD.replace("## Fix\n", f"## Fix\n```\n{cut}\n```\n")
        result = run_script("findings", "check", write(tmp_path, text, "cut.md"))
        assert result.returncode == 1 and "secret" in result.stdout, cut


def test_where_merge_handles_crlf_and_spaced_headings(tmp_path):
    new, audit = tmp_path / "new", tmp_path / "audit"
    new.mkdir()
    audit.mkdir()
    first = GOOD.replace("## Where", "##  Where  ").replace("\n", "\r\n")
    second = (GOOD.replace("**Severity:** high", "**Severity:** low")
              .replace("- `src/routes/orders.js:12` (GET /orders/:id)",
                       "- `src/routes/admin.js:40` (GET /admin/orders/:id)"))
    (new / "a.md").write_bytes(first.encode())
    (new / "b.md").write_text(second, encoding="utf-8")
    assert run_script("findings", "dedupe", new, audit).returncode == 0
    [kept] = list(new.glob("*.md"))
    text = kept.read_text(encoding="utf-8")
    assert "src/routes/admin.js:40" in text
    where = text.split("Where")[1].split("## Evidence")[0]
    assert "src/routes/admin.js:40" in where
    assert run_script("findings", "check", kept).returncode == 0


def test_one_line_key_bodies_are_fingerprinted_and_urls_are_not(make_repo, tmp_path):
    from test_secrets_scan import BEGIN, BODY, END

    repo = make_repo({
        ".env": f'GCP_KEY="{BEGIN}\\n{BODY}\\n{END}\\n"\nTOKEN_TYPE=Bearer\n'
                "OAUTH_TOKEN_URL=https://auth.corp.test/oauth/token\n",
        "src/pem.js": f'const HEADER = "{BEGIN}";\nexport function parsePem(text) {{\n'
                      "  return text.split(String.fromCharCode(10)).filter(Boolean);\n}\n",
    })
    prints = tmp_path / "fingerprints.json"
    assert run_script("secrets_scan", repo, "--fingerprints", prints).returncode == 0

    leak = GOOD.replace("## Fix\n", f"## Fix\n```\n{BODY[10:50]}\n```\n")
    result = run_script("findings", "check", write(tmp_path, leak, "leak.md"),
                        "--fingerprints", prints)
    assert result.returncode == 1 and "secret" in result.stdout

    fine = GOOD.replace("## Fix\n", "## Fix\nSend `Authorization: Bearer <redacted>` to "
                        "https://auth.corp.test/oauth/token; `parsePem(text)` splits with "
                        "`text.split(String.fromCharCode(10)).filter(Boolean)`; keys look like "
                        "`sk-ant-api03-...`.\n")
    result = run_script("findings", "check", write(tmp_path, fine, "fine.md"),
                        "--fingerprints", prints)
    assert result.returncode == 0, result.stdout

    for bad in ('{"values": []}', '{"lengths": 5, "values": [], "windows": []}'):
        prints.write_text(bad, encoding="utf-8")
        result = run_script("findings", "check", write(tmp_path, GOOD, "g.md"),
                            "--fingerprints", prints)
        assert result.returncode == 1 and "Traceback" not in result.stderr, bad


def test_key_bodies_in_every_layout_and_slash_secrets_are_fingerprinted(make_repo, tmp_path):
    from test_secrets_scan import BEGIN, BODY, END

    slash_line = "/Rk4AbCdZq9TxW2vLp8" + "Qw3Er5Ty7Ui9Op1As" * 2
    concat = "Zq9TxW2vLp8Rk4Ab" + "Cd5Ef7Gh9Ij1Kl3Mn" * 2
    legacy = "Lg8Hy6Tf4Rd2Se0Wa" + "Qz7Xs5Cd3Vf1Bg9Nh" * 2
    env_secret = "/Zq9TxW2vLp8" + "Rk4AbCdEfGh"
    repo = make_repo({
        "keys/a.pem": f"{BEGIN}\n{BODY}\n{slash_line}\n{END}\n",
        "src/Fixture.java": f'String KEY = "{BEGIN}\\n" +\n    "{concat}\\n" +\n'
                            f'    "{BODY[:48]}\\n" +\n    "{END}\\n";\nint after = 1;\n',
        "keys/old.pem": f"{BEGIN}\nProc-Type: 4,ENCRYPTED\nDEK-Info: AES-128-CBC,AB12CD34\n\n"
                        f"{legacy}\n{END}\n",
        ".env": f"AWS_SECRET_ACCESS_KEY={env_secret}\n"
                f'GCP_KEY={{"private_key":"{BEGIN}\\n{BODY}\\n{END}\\n",'
                '"token_uri":"https://oauth2.googleapis.com/token"}\n',
        "src/cfg.js": 'const keyFile = "certs/server1.pem";\nconst keyDir = "/usr/local/keys";\n',
    })
    prints = tmp_path / "fingerprints.json"
    scan = run_script("secrets_scan", repo, "--fingerprints", prints)
    assert scan.returncode == 0, scan.stderr
    found = {(f["path"], f["line"]) for f in json.loads(scan.stdout)}
    assert (".env", 1) in found
    assert ("src/cfg.js", 1) not in found and ("src/cfg.js", 2) not in found

    for leak in (slash_line[5:45], concat[3:40], legacy[2:40], env_secret):
        text = GOOD.replace("## Fix\n", f"## Fix\n```\n{leak}\n```\n")
        result = run_script("findings", "check", write(tmp_path, text, "leak.md"),
                            "--fingerprints", prints)
        assert result.returncode == 1 and "secret" in result.stdout, leak

    fine = GOOD.replace("## Fix\n", "## Fix\nThe token URI is "
                        "https://oauth2.googleapis.com/token; keys live in `/usr/local/keys` "
                        "and `certs/server1.pem`.\n")
    result = run_script("findings", "check", write(tmp_path, fine, "fine.md"),
                        "--fingerprints", prints)
    assert result.returncode == 0, result.stdout


# --- The deploy verdict (2026-11-20-m-audit-verdict) ---

TODAY = __import__("datetime").date.today().isoformat()


def clean_facts(tmp_path):
    """A run that covered everything: the scope, run facts and re-check of a clean audit."""
    scope = {
        "parts": [{"id": 1, "dir": "src/routes", "files": ["src/routes/orders.js"],
                   "stacks": ["node"], "checklists": ["generic", "pii", "node"],
                   "no_checklist": []},
                  {"id": 2, "dir": "src/services", "files": ["src/services/orders.js"],
                   "stacks": ["node"], "checklists": ["generic", "pii", "node"],
                   "no_checklist": []}],
        "skipped": [],
        "audits": [{"dir": ".", "lockfile": "package-lock.json",
                    "command": "npm audit --omit=dev --json",
                    "step": "npm audit --omit=dev --json"}],
        "coverage": {"paths": [], "commit": "abc1234def5678", "dirty": False,
                     "unsafe_folders": [], "other_files": {}, "manifests_without_lockfile": [],
                     "unaudited_lockfiles": []},
    }
    meta = {"policy": True, "secrets_scanned": True, "audited": ["package-lock.json"],
            "audit_failures": [], "check_failed": []}
    recheck = {"fixed": [], "still_open": [], "cannot_check": [], "not_rechecked": []}
    return scope, meta, recheck


def report_for(tmp_path, audit, scope=None, meta=None, recheck=None, extra=()):
    args = []
    for name, data in (("scope", scope), ("meta", meta), ("recheck", recheck)):
        if data is not None:
            path = tmp_path / f"{name}.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            args += [f"--{name}", path]
    result = run_script("findings", "report", audit, *args, *extra)
    assert result.returncode == 0, result.stderr
    return (audit / "REPORT.md").read_text(encoding="utf-8")


def verdict(report):
    return next(line for line in report.splitlines() if line.startswith("## Verdict:"))


def audit_with(tmp_path, *texts):
    audit = tmp_path / "home" / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    for n, text in enumerate(texts, 1):
        (audit / f"{n:02d}.md").write_text(text, encoding="utf-8")
    return audit


def scripted(tmp_path, kind, data, name):
    out = tmp_path / f"out-{name}"
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_script("findings", kind, path, out)
    assert result.returncode == 0, result.stderr
    [found] = sorted(out.glob("*.md"))
    return found.read_text(encoding="utf-8")


SECRET_SCAN = [{"path": ".env", "line": 3, "pattern": "stripe-live-key", "length": 32,
                "committed": True, "severity": "critical", "id": "1f2e3d4c5b6a7980"}]
COMPOSER = {"advisories": {"guzzlehttp/psr7": [
    {"advisoryId": "PKSA-1", "title": "Header injection", "affectedVersions": "<1.8.4",
     "severity": "high", "cve": "CVE-2022-24775", "link": "https://x"}]}}
MEDIUM = GOOD.replace("**Severity:** high", "**Severity:** medium")


def test_verdict_blocks_on_open_critical_or_high(tmp_path):
    scope, meta, recheck = clean_facts(tmp_path)
    secret = scripted(tmp_path, "from-secrets-scan", SECRET_SCAN, "secret")
    advisory = scripted(tmp_path, "from-composer-audit", COMPOSER, "composer")
    for text, words in ((GOOD, ["01 (high)"]), (secret, ["01 (critical)"]),
                        (advisory, ["01 (high)",
                                    "no fix known: replace the package or accept it with a date"])):
        audit = audit_with(tmp_path / text[:20].replace(" ", "_").replace("#", ""), MEDIUM)
        (audit / "01.md").write_text(text, encoding="utf-8")
        (audit / "02.md").write_text(MEDIUM, encoding="utf-8")
        report = report_for(tmp_path, audit, scope, meta, recheck)
        assert report.splitlines()[0] == "# Security and PII audit"
        assert verdict(report) == "## Verdict: Blocked", report
        top = report.split("## Findings")[0]
        for word in words:
            assert word in top, (word, top)
        assert "02 (medium)" not in top


def test_verdict_is_not_verified_for_each_gap(tmp_path):
    def gap(change):
        scope, meta, recheck = clean_facts(tmp_path)
        change(scope, meta, recheck)
        return scope, meta, recheck

    cases = {
        "--max": gap(lambda s, m, r: s["skipped"].append(
            {"id": 3, "dir": "lib", "files": ["lib/a.js", "lib/b.js"], "stacks": ["node"]})),
        "only part of the repo": gap(lambda s, m, r: s["coverage"]["paths"].append("src")),
        "unsafe": gap(lambda s, m, r: s["coverage"]["unsafe_folders"].append("a$(id)")),
        "no checklist of its own for python": gap(
            lambda s, m, r: s["parts"][0]["no_checklist"].append("python")),
        "no checklist of its own for react": gap(
            lambda s, m, r: s["parts"][1]["no_checklist"].append("react")),
        "2 files in .sh": gap(lambda s, m, r: s["coverage"]["other_files"].update({".sh": 2})),
        "lockfile with no dependency audit: svc/go.sum": gap(
            lambda s, m, r: s["coverage"]["unaudited_lockfiles"].append("svc/go.sum")),
        "dependency audit didn't run or failed: package-lock.json (offline)": gap(
            lambda s, m, r: (m.update(audited=[]), m["audit_failures"].append(
                {"lockfile": "package-lock.json", "reason": "offline"}))),
        "manifest with no lockfile: api/package.json": gap(
            lambda s, m, r: s["coverage"]["manifests_without_lockfile"].append(
                "api/package.json")),
        "uncommitted changes": gap(lambda s, m, r: s["coverage"].update(dirty=True)),
        "couldn't tell whether there are uncommitted changes": gap(
            lambda s, m, r: s["coverage"].update(dirty=None)),
        "couldn't tell which commit": gap(lambda s, m, r: s["coverage"].update(commit=None)),
        "secrets scan didn't run": gap(lambda s, m, r: m.update(secrets_scanned=False)),
        "agent-3.md failed the format check": gap(lambda s, m, r: m["check_failed"].append(
            {"file": "agent-3.md", "problems": ["missing section: ## Fix"]})),
        "07 couldn't be re-checked": gap(lambda s, m, r: r["cannot_check"].append(
            {"number": "07", "reason": "needs a running service"})),
        "2 earlier findings not re-checked: outside this run's scope (07, 09)": gap(
            lambda s, m, r: r["not_rechecked"].extend(["07", "09"])),
    }
    for n, (words, (scope, meta, recheck)) in enumerate(cases.items()):
        audit = audit_with(tmp_path / f"case{n}", MEDIUM)
        report = report_for(tmp_path, audit, scope, meta, recheck)
        assert verdict(report) == "## Verdict: Not verified", (words, report)
        assert words in report.split("## Findings")[0], (words, report)

    # Facts nobody reported, and a finding the report can't read, are gaps, never clean.
    scope, meta, recheck = clean_facts(tmp_path)
    for n, (args, words) in enumerate(((dict(meta=meta, recheck=recheck), "--scope"),
                                       (dict(scope=scope, recheck=recheck), "run facts"),
                                       (dict(scope=scope, meta=meta), "re-check"))):
        audit = audit_with(tmp_path / f"missing{n}", MEDIUM)
        report = report_for(tmp_path, audit, **args)
        assert verdict(report) == "## Verdict: Not verified" and words in report, words
    audit = audit_with(tmp_path / "broken", MEDIUM, "# broken, was critical\n")
    report = report_for(tmp_path, audit, scope, meta, recheck)
    assert verdict(report) == "## Verdict: Not verified"
    assert "02.md fails the format check" in report.split("## Findings")[0]


def test_verdict_safe_only_with_full_coverage_and_names_the_commit(tmp_path):
    scope, meta, recheck = clean_facts(tmp_path)
    low = GOOD.replace("**Severity:** high", "**Severity:** low").replace("# Any", "# Low: any")
    audit = audit_with(tmp_path, MEDIUM, low)
    report = report_for(tmp_path, audit, scope, meta, recheck)
    assert verdict(report) == "## Verdict: Safe to deploy", report
    top = report.split("## Findings")[0]
    for words in ("abc1234def5678", TODAY, "code only, no live environment",
                  "no uncommitted changes"):
        assert words in top, words
    assert "| 01 | medium |" in report and "| 02 | low |" in report

    empty = audit_with(tmp_path / "empty")
    assert verdict(report_for(tmp_path, empty, scope, meta, recheck)) == (
        "## Verdict: Safe to deploy")


def test_accepted_findings_expire_and_bad_lines_accept_nothing(tmp_path):
    scope, meta, recheck = clean_facts(tmp_path)
    audit = audit_with(tmp_path, GOOD, GOOD.replace("# Any user", "# Admin open"), MEDIUM)
    accepted = audit.parent / "accepted.md"
    accepted.write_bytes((
        "# Accepted\n\n"
        "- 01 until 2999-12-31: fixing in sprint 4\n"
        "- 02 until 2000-01-01: was fine last year\r\n"
        "- 07 until 2999-12-31: no such finding\n"
        "- 03 until 31/12/2999: bad date\n"
        "- 03: no date at all\n"
        "- 03 rotated: not a secret\n"
        "- ０３ until 2999-12-31: fullwidth digits\n"
        "- 99999999999999999999 until 2999-12-31: huge\n"
        "- 03 until 9999-99-99: impossible date\n").encode())
    report = report_for(tmp_path, audit, scope, meta, recheck)
    top = report.split("## Findings")[0]
    assert verdict(report) == "## Verdict: Blocked"
    blocking = top.split("## Verdict: Blocked")[1].split("\n\n")[1]
    assert "02 (high)" in blocking and "acceptance expired" in blocking
    assert "01 (high)" not in blocking
    assert "01 (high) until 2999-12-31" in report and "fixing in sprint 4" in report
    invalid = report.split("Invalid lines in accepted.md")[1]
    assert invalid.count("- line ") == 7, invalid
    assert "Traceback" not in report

    accepted.write_text("- 01 until 2999-12-31: fixing in sprint 4\n", encoding="utf-8")
    (audit / "02.md").unlink()
    assert verdict(report_for(tmp_path, audit, scope, meta, recheck)) == (
        "## Verdict: Safe to deploy")

    accepted.write_bytes(b"- 01 until 2999-12-31: caf\xe9\n")
    report = report_for(tmp_path, audit, scope, meta, recheck)
    assert verdict(report) == "## Verdict: Blocked" and "isn't UTF-8" in report


def recheck(tmp_path, audit, scope, *args):
    path = tmp_path / "scope.json"
    path.write_text(json.dumps(scope), encoding="utf-8")
    out = tmp_path / "recheck.json"
    result = run_script("findings", "recheck", audit, "--scope", path, "--out", out, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(out.read_text(encoding="utf-8"))


NPM = {"vulnerabilities": {"lodash": {
    "name": "lodash", "severity": "high", "range": "<4.17.21",
    "via": [{"title": "Prototype Pollution", "cwe": ["CWE-1321"],
             "url": "https://github.com/advisories/GHSA-x"}],
    "fixAvailable": {"name": "lodash", "version": "4.17.21"}}}}


def test_scripted_findings_fixed_when_gone_but_committed_secrets_need_rotation(tmp_path,
                                                                              make_repo):
    scope, meta, _ = clean_facts(tmp_path)
    # A repo whose history never held .env, and whose composer.lock is still there.
    repo = make_repo({"composer.lock": "{}"})
    advisory = scripted(tmp_path, "from-npm-audit", NPM, "npm")
    local = scripted(tmp_path, "from-secrets-scan",
                     [{**SECRET_SCAN[0], "committed": False, "id": "aaaa"}], "local")
    committed = scripted(tmp_path, "from-secrets-scan", SECRET_SCAN, "committed")
    php = scripted(tmp_path, "from-composer-audit", COMPOSER, "php")
    audit = audit_with(tmp_path, advisory, local, committed, php)
    found = tmp_path / "found"
    found.mkdir()

    # A producer that didn't run proves nothing: everything stays open.
    result = recheck(tmp_path, audit, scope, "--found", found)
    assert result["fixed"] == [] and len(list(audit.glob("0*.md"))) == 4

    result = recheck(tmp_path, audit, scope, "--found", found, "--secrets-scanned",
                     "--audited", "package-lock.json", "--repo", repo)
    assert sorted(f["number"] for f in result["fixed"]) == ["01", "02"]
    for n in ("01", "02"):
        assert not (audit / f"{n}.md").exists()
        moved = (audit / "fixed" / f"{n}.md").read_text(encoding="utf-8")
        assert TODAY in moved.splitlines()[-1] and "no longer" in moved.splitlines()[-1]
        assert mode_is(audit / "fixed" / f"{n}.md", 0o600)
    assert (audit / "03.md").exists() and (audit / "04.md").exists()
    assert run_script("findings", "next", audit).stdout.strip() == "05"

    # A crash between writing fixed/NN.md and removing NN.md: it counts as fixed.
    (audit / "fixed" / "03.md").write_text(committed, encoding="utf-8")
    report = report_for(tmp_path, audit, scope, meta,
                        {"fixed": [], "still_open": [], "cannot_check": [], "not_rechecked": []})
    assert "| 03 |" not in report
    (audit / "fixed" / "03.md").unlink()

    (audit.parent / "accepted.md").write_text(
        "- 03 rotated: rotated 2026-11-20 in the vault\n- 04 rotated: not a secret\n",
        encoding="utf-8")
    meta["audited"] = ["package-lock.json"]
    report = report_for(tmp_path, audit, scope, meta,
                        {"fixed": [], "still_open": [], "cannot_check": [], "not_rechecked": []})
    blocking = report.split("## Findings")[0]
    assert "03 (critical)" not in blocking.split("Accepted")[0]
    assert "04 (high)" in blocking and "rotated: rotated 2026-11-20" in report
    assert "Invalid lines in accepted.md" in report


def test_findings_keep_their_number_when_code_moves(tmp_path, make_repo):
    first = scripted(tmp_path, "from-secrets-scan", SECRET_SCAN, "first")
    advisory = scripted(tmp_path, "from-npm-audit", NPM, "npm1")
    audit = audit_with(tmp_path, first, advisory)
    new = tmp_path / "new"
    moved = [{**SECRET_SCAN[0], "line": 9}]
    other = [{**SECRET_SCAN[0], "line": 3, "id": "ffffeeeeddddcccc"}]
    for name, data in (("moved", moved), ("other", other)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert run_script("findings", "from-secrets-scan", path, new).returncode == 0
    again = json.loads(json.dumps(NPM))
    again["vulnerabilities"]["lodash"]["range"] = "<4.17.22"
    path = tmp_path / "again.json"
    path.write_text(json.dumps(again), encoding="utf-8")
    assert run_script("findings", "from-npm-audit", path, new).returncode == 0
    result = run_script("findings", "dedupe", new, audit)
    assert result.returncode == 0, result.stderr
    [left] = new.glob("*.md")
    # A different secret in the same place (a new key after rotation) is a new finding.
    assert "ffffeeeeddddcccc" in left.read_text(encoding="utf-8")

    # The id is a keyed digest: stable when the line moves, never the value or a plain hash.
    value = "sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc"
    repo = make_repo({".env": f"STRIPE_KEY={value}\n"})
    key = tmp_path / "home" / "secret-id.key"
    ids = []
    for text in (f"STRIPE_KEY={value}\n", f"# moved\n\nSTRIPE_KEY={value}\n",
                 f"STRIPE_KEY={value[:-1]}X\n"):
        (repo / ".env").write_text(text, encoding="utf-8")
        scan = run_script("secrets_scan", repo, "--id-key", key)
        assert scan.returncode == 0, scan.stderr
        [item] = json.loads(scan.stdout)
        ids.append(item["id"])
        assert value not in scan.stdout and value[8:20] not in scan.stdout
    assert ids[0] == ids[1] != ids[2]
    assert mode_is(key, 0o600)
    import hashlib
    assert ids[0] not in hashlib.sha256(value.encode()).hexdigest()


def test_recheck_verdicts_update_earlier_findings(tmp_path):
    scope, meta, _ = clean_facts(tmp_path)
    second = GOOD.replace("# Any user", "# Refund without role")
    third = GOOD.replace("# Any user", "# Export open")
    outside = GOOD.replace("src/routes/orders.js:12", "other/x.js:3").replace(
        "src/services/orders.js:30", "other/x.js:9").replace("# Any user", "# Other")
    audit = audit_with(tmp_path, GOOD, second, third, outside)
    # Outside means left out by this run's limits: here a paths… argument.
    scope["coverage"]["paths"] = ["src"]
    scope_file = tmp_path / "scope.json"
    scope_file.write_text(json.dumps(scope), encoding="utf-8")
    listed = run_script("findings", "earlier", audit, "--scope", scope_file)
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout) == {"recheck": ["01", "02", "03"], "outside": ["04"]}

    verdicts = tmp_path / "verdicts.json"
    verdicts.write_text(json.dumps({
        "01": "I looked.\nVERDICT: STILL OPEN at src/services/orders.js:34",
        "02": "VERDICT: FIXED — ownership check added at src/services/orders.js:31",
    }), encoding="utf-8")
    result = recheck(tmp_path, audit, scope, "--verdicts", verdicts)
    assert result["still_open"] == ["01"]
    assert [f["number"] for f in result["fixed"]] == ["02"]
    assert [c["number"] for c in result["cannot_check"]] == ["03"]
    assert result["not_rechecked"] == ["04"]

    kept = (audit / "01.md").read_text(encoding="utf-8")
    assert kept.startswith(GOOD) and "src/services/orders.js:34" in kept.splitlines()[-1]
    assert TODAY in kept.splitlines()[-1]
    fixed = (audit / "fixed" / "02.md").read_text(encoding="utf-8")
    assert fixed.startswith(second) and "ownership check added" in fixed.splitlines()[-1]
    assert (audit / "03.md").exists() and (audit / "04.md").exists()

    new = tmp_path / "new"
    new.mkdir()
    (new / "a.md").write_text(GOOD.replace("orders.js:30", "orders.js:34"), encoding="utf-8")
    assert run_script("findings", "dedupe", new, audit).returncode == 0
    assert list(new.glob("*.md")) == []


def test_worth_a_look_lists_unconfirmed_without_blocking(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path)
    (audit / "unconfirmed").mkdir()
    (audit / "unconfirmed" / "old.md").write_text("old suspect", encoding="utf-8")
    src = tmp_path / "suspects"
    src.mkdir()
    critical = GOOD.replace("**Severity:** high", "**Severity:** critical")
    (src / "agent-1.md").write_text(critical, encoding="utf-8")
    (src / "agent-1.verdict").write_text(
        "VERDICT: NOT CONFIRMED — ownership filter at src/db/scope.js:4\n", encoding="utf-8")
    (src / "agent-2.md").write_text(GOOD.replace("# Any user", "# Maybe SSRF"),
                                    encoding="utf-8")
    (src / "agent-2.verdict").write_text("VERDICT: CANNOT CHECK — needs a running service",
                                         encoding="utf-8")
    (src / "agent-3.md").write_text("# broken\n", encoding="utf-8")
    (src / "agent-3.verdict").write_text("VERDICT: NOT CONFIRMED — x", encoding="utf-8")
    result = run_script("findings", "suspects", src, audit)
    assert result.returncode == 0, result.stderr
    kept = sorted(p.name for p in (audit / "unconfirmed").iterdir())
    assert kept == ["agent-1.md", "agent-2.md"]
    for name in kept:
        assert mode_is(audit / "unconfirmed" / name, 0o600)
    assert run_script("findings", "next", audit).stdout.strip() == "01"

    report = report_for(tmp_path, audit, scope, meta, recheck_)
    assert verdict(report) == "## Verdict: Safe to deploy"
    look = report.split("## Worth a look (unconfirmed, doesn't block)")[1]
    for words in ("Any user can read any order by id", "`src/routes/orders.js:12`", "critical",
                  "NOT CONFIRMED — ownership filter at src/db/scope.js:4", "Maybe SSRF",
                  "CANNOT CHECK — needs a running service"):
        assert words in look, words

    meta["check_failed"] = [{"file": "agent-3.md", "problems": ["missing section: ## Fix"]}]
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    look = report.split("## Worth a look (unconfirmed, doesn't block)")[1]
    assert "agent-3.md: missing section: ## Fix" in look


def test_owasp_tags_and_coverage_table(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    sqli = MEDIUM.replace("CWE-639", "CWE-89").replace("**Category:** authz",
                                                       "**Category:** injection")
    nosql = MEDIUM.replace("CWE-639", "CWE-943").replace("# Any user", "# NoSQL")
    audit = audit_with(tmp_path, MEDIUM, sqli, nosql)
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    rows = {line.split("|")[1].strip(): line for line in report.splitlines()
            if line.startswith("| 0")}
    assert "| A01 |" in rows["01"] and "| A05 |" in rows["02"] and "| unmapped |" in rows["03"]
    table = report.split("## OWASP Top 10 (2025)")[1]
    assert "| A01 | Broken Access Control | checked | 0 | 0 | 1 | 0 |" in table
    assert "| A03 | Software Supply Chain Failures | not checked | 0 | 0 | 0 | 0 |" in table
    assert sum(line.startswith("| A") for line in table.splitlines()) == 10


def test_new_report_sections_withhold_known_secrets(make_repo, tmp_path):
    value = "letmein" + "nowplease" + "2024"
    repo = make_repo({".env": f"DB_PASSWORD={value}\n"})
    prints = tmp_path / "fingerprints.json"
    assert run_script("secrets_scan", repo, "--fingerprints", prints).returncode == 0
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path, GOOD, GOOD.replace("# Any user", "# Second"))

    src = tmp_path / "suspects"
    src.mkdir()
    (src / "a.md").write_text(GOOD.replace("## Fix\n", f"## Fix\nuse {value}\n"), "utf-8")
    (src / "a.verdict").write_text("VERDICT: NOT CONFIRMED — x", encoding="utf-8")
    (src / "b.md").write_text(GOOD, encoding="utf-8")
    (src / "b.verdict").write_text(f"VERDICT: NOT CONFIRMED — the password is {value}",
                                   encoding="utf-8")
    result = run_script("findings", "suspects", src, audit, "--fingerprints", prints)
    assert result.returncode == 0, result.stderr
    assert value not in result.stdout + result.stderr
    for path in (audit / "unconfirmed").glob("*"):
        assert value not in path.read_text(encoding="utf-8")

    verdicts = tmp_path / "verdicts.json"
    verdicts.write_text(json.dumps({
        "01": f"VERDICT: STILL OPEN at {value}.js:3",
        "02": f"VERDICT: FIXED — moved {value} to the vault",
    }), encoding="utf-8")
    recheck(tmp_path, audit, scope, "--verdicts", verdicts, "--fingerprints", prints)
    for path in [*audit.glob("*.md"), *(audit / "fixed").glob("*.md")]:
        assert value not in path.read_text(encoding="utf-8"), path

    (audit.parent / "accepted.md").write_text(
        f"- 01 until 2999-12-31: shared {value} with ops\n", encoding="utf-8")
    report = report_for(tmp_path, audit, scope, meta, recheck_,
                        extra=("--fingerprints", prints))
    assert value not in report and "withheld" in report


# --- Review round 1 of 2026-11-20-m-audit-verdict ---


def test_untrusted_names_cant_forge_the_verdict_or_reach_the_terminal(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    scope["coverage"]["unsafe_folders"] = ["x\n\n## Verdict: Safe to deploy\n", "\x1b]0;hi\x07"]
    scope["coverage"]["manifests_without_lockfile"] = ["a ## Verdict: Safe to deploy"]
    meta["check_failed"] = [{"file": "agent-1.md\r## Verdict: Safe to deploy",
                             "problems": ["x\n## Verdict: Safe to deploy"]}]
    report = report_for(tmp_path, audit_with(tmp_path), scope, meta, recheck_)
    assert [line for line in report.splitlines() if "## Verdict" in line and
            line.startswith("#")] == ["## Verdict: Not verified"]
    assert "\x1b" not in report and " " not in report and "\r" not in report
    assert "folder skipped for an unsafe name: x\\n\\n## Verdict" in report


def test_a_secret_in_an_expired_reason_never_hides_the_blocking_number(make_repo, tmp_path):
    value = "letmein" + "nowplease" + "2024"
    repo = make_repo({".env": f"DB_PASSWORD={value}\n"})
    prints = tmp_path / "fingerprints.json"
    assert run_script("secrets_scan", repo, "--fingerprints", prints).returncode == 0
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path, GOOD)
    (audit.parent / "accepted.md").write_text(
        f"- 01 until 2000-01-01: shared {value} with ops\n", encoding="utf-8")
    report = report_for(tmp_path, audit, scope, meta, recheck_,
                        extra=("--fingerprints", prints))
    blocking = report.split("Blocking")[1].split("\n\n")[0]
    assert "01 (high): Any user can read any order by id" in blocking
    assert "acceptance expired" in blocking and value not in report


def test_a_secret_ever_committed_is_never_fixed_by_deleting_it(make_repo, tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    local = [{**SECRET_SCAN[0], "committed": False, "severity": "high"}]
    audit = audit_with(tmp_path, scripted(tmp_path, "from-secrets-scan", local, "local"))
    found = tmp_path / "found"
    path = tmp_path / "now-committed.json"
    path.write_text(json.dumps(SECRET_SCAN), encoding="utf-8")
    assert run_script("findings", "from-secrets-scan", path, found).returncode == 0
    recheck(tmp_path, audit, scope, "--found", found, "--secrets-scanned")
    assert "committed" in (audit / "01.md").read_text(encoding="utf-8").splitlines()[-1]
    empty = tmp_path / "empty"
    empty.mkdir()
    result = recheck(tmp_path, audit, scope, "--found", empty, "--secrets-scanned")
    assert result["fixed"] == [] and (audit / "01.md").exists()

    # Committed and deleted between two runs: git history says so.
    repo = make_repo({".env": "x\n"})
    from conftest import commit, git
    commit(repo)
    git(repo, "rm", "-q", ".env")
    commit(repo, "remove")
    audit2 = audit_with(tmp_path / "two", scripted(tmp_path, "from-secrets-scan", local, "l2"))
    result = recheck(tmp_path, audit2, scope, "--found", empty, "--secrets-scanned",
                     "--repo", repo)
    assert result["fixed"] == [] and (audit2 / "01.md").exists()


def test_a_malformed_scope_is_one_error_line(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path, MEDIUM)
    bad = []
    for key, value in (("unsafe_folders", 5), ("paths", 7), ("other_files", ["x"]),
                       ("dirty", "no"), ("dirty", 1), ("dirty", 0), ("commit", 3),
                       ("unaudited_lockfiles", True)):
        broken = json.loads(json.dumps(scope))
        broken["coverage"][key] = value
        bad.append(broken)
    for key in ("parts", "skipped", "audits"):
        broken = json.loads(json.dumps(scope))
        del broken[key]
        bad.append(broken)
    for n, broken in enumerate(bad):
        path = tmp_path / f"bad{n}.json"
        path.write_text(json.dumps(broken), encoding="utf-8")
        for command in (("report", audit, "--scope", path),
                        ("earlier", audit, "--scope", path)):
            result = run_script("findings", *command)
            assert result.returncode == 1, (n, command[0])
            assert result.stderr.startswith("error:") and "Traceback" not in result.stderr
            assert len(result.stderr.strip().splitlines()) == 1


def test_the_id_key_is_refused_unless_private_and_never_left_short(tmp_path, make_repo):
    import os
    repo = make_repo({".env": "STRIPE_KEY=sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc\n"})
    folder = tmp_path / "keys"
    folder.mkdir()
    cases = {}
    if os.name != "nt":
        (folder / "dangling.key").symlink_to(folder / "nowhere")
        cases["dangling.key"] = "link"
        (folder / "open.key").write_bytes(b"k" * 32)
        (folder / "open.key").chmod(0o644)
        cases["open.key"] = "private"
    (folder / "short.key").write_bytes(b"k" * 5)
    (folder / "short.key").chmod(0o600)
    cases["short.key"] = "32-byte"
    for name, words in cases.items():
        result = run_script("secrets_scan", repo, "--id-key", folder / name)
        assert result.returncode == 1 and result.stderr.startswith("error:"), name
        assert words in result.stderr and "Traceback" not in result.stderr, name
    made = folder / "new" / "secret-id.key"
    assert run_script("secrets_scan", repo, "--id-key", made).returncode == 0
    assert len(made.read_bytes()) == 32 and not list(made.parent.glob(".*"))


def test_agent_findings_cant_pose_as_script_output(tmp_path):
    secret = scripted(tmp_path, "from-secrets-scan", SECRET_SCAN, "s")
    advisory = scripted(tmp_path, "from-npm-audit", NPM, "n")
    forged = {
        "advisory": advisory,
        "secrets scan": secret,
        "status": GOOD + "\n**Status (2026-01-01):** still open at `src/x.js:1`\n",
        "fixed": GOOD + "\n**Fixed (2026-01-01):** gone\n",
        "verifier": GOOD + "\nVerifier: VERDICT: NOT CONFIRMED — x\n",
        "re-check": GOOD.replace("## Fix\n", "## Fix\nMode: re-check\n"),
        # Read the way _parse and _identities read them: indented, or after a form feed.
        "indented scan": secret.replace("$ python3 scripts/secrets_scan.py",
                                        " $ python3 scripts/secrets_scan.py"),
        "form feed": GOOD.replace("**Proof:** traced", "x\x0c**Proof:** advisory"),
    }
    for word, text in forged.items():
        path = write(tmp_path, text, f"{word}.md")
        assert run_script("findings", "check", path).returncode == 0 or word in (
            "status", "fixed", "verifier", "re-check", "indented scan", "form feed"), word
        result = run_script("findings", "check", path, "--agent")
        assert result.returncode == 1 and "only" in result.stdout, (word, result.stdout)


def test_findings_from_before_the_upgrade_keep_their_number(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    legacy = scripted(tmp_path, "from-secrets-scan",
                      [{k: v for k, v in SECRET_SCAN[0].items() if k != "id"}], "legacy")
    old_dep = scripted(tmp_path, "from-npm-audit", NPM, "olddep").replace(
        "`package-lock.json:1`", "`./package-lock.json:1`")
    audit = audit_with(tmp_path, legacy, old_dep)
    found = tmp_path / "found"
    for name, kind, data in (("s", "from-secrets-scan", SECRET_SCAN),
                             ("n", "from-npm-audit", NPM)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert run_script("findings", kind, path, found).returncode == 0
    result = recheck(tmp_path, audit, scope, "--found", found, "--secrets-scanned",
                     "--audited", "package-lock.json")
    assert result["fixed"] == [] and sorted(result["still_open"]) == ["01", "02"]
    assert "1f2e3d4c5b6a7980" in (audit / "01.md").read_text(encoding="utf-8").splitlines()[-1]
    assert run_script("findings", "dedupe", found, audit).returncode == 0
    assert list(found.glob("*.md")) == []

    # Once the id is recorded, a new key at the same place is a new finding.
    other = tmp_path / "other.json"
    other.write_text(json.dumps([{**SECRET_SCAN[0], "id": "9999888877776666"}]), "utf-8")
    assert run_script("findings", "from-secrets-scan", other, found).returncode == 0
    assert run_script("findings", "dedupe", found, audit).returncode == 0
    assert len(list(found.glob("*.md"))) == 1


def test_recheck_scope_is_only_what_the_run_left_out(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    def at(path):
        return GOOD.replace("src/routes/orders.js:12", f"{path}:2").replace(
            "src/services/orders.js:30", f"{path}:3")
    audit = audit_with(tmp_path, at("views/order.ejs"), at("lib/gone.js"), at("lib/skip.js"))
    scope["skipped"] = [{"id": 3, "dir": "lib", "files": ["lib/skip.js"], "stacks": ["node"]}]
    path = tmp_path / "scope.json"
    path.write_text(json.dumps(scope), encoding="utf-8")
    listed = json.loads(run_script("findings", "earlier", audit, "--scope", path).stdout)
    assert listed == {"recheck": ["01", "02"], "outside": ["03"]}
    scope["coverage"]["paths"] = ["views"]
    path.write_text(json.dumps(scope), encoding="utf-8")
    listed = json.loads(run_script("findings", "earlier", audit, "--scope", path).stdout)
    assert listed == {"recheck": ["01"], "outside": ["02", "03"]}


def test_recheck_reads_spaced_locations_and_names_unreadable_verdicts(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    repo = tmp_path / "my repo"
    (repo / "src dir").mkdir(parents=True)
    (repo / "src dir" / "ö.js").write_text("a\nb\nc\n", encoding="utf-8")
    for name in ("src/routes/orders.js", "src/services/orders.js"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text("x\n" * 40, encoding="utf-8")
    audit = audit_with(tmp_path, *[GOOD.replace("# Any user", f"# F{n}") for n in range(6)])
    verdicts = tmp_path / "v.json"
    verdicts.write_text(json.dumps({
        "01": "VERDICT: STILL OPEN at `src dir/ö.js:2`",
        "02": "VERDICT: STILL OPEN at src/services/orders.js:99",
        "03": "VERDICT: still open, probably",
        "05": "VERDICT: CANNOT CHECK - needs a running queue",
        "06": "VERDICT: STILL OPEN at `src/services/orders.js:30`",
    }), encoding="utf-8")
    result = recheck(tmp_path, audit, scope, "--verdicts", verdicts, "--repo", repo)
    assert sorted(result["still_open"]) == ["01", "06"]
    reasons = {c["number"]: c["reason"] for c in result["cannot_check"]}
    assert "real line" in reasons["02"] and "couldn't be read" in reasons["03"]
    assert reasons["04"] == "no re-check verdict" and reasons["05"] == "needs a running queue"
    before = (audit / "06.md").read_bytes()
    recheck(tmp_path, audit, scope, "--verdicts", verdicts, "--repo", repo)
    assert (audit / "06.md").read_bytes() == before
    report = report_for(tmp_path, audit, scope, None, None)
    assert "`src dir/ö.js:2`" in report


def test_rejected_suspects_and_missing_verdicts_reach_the_report(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path)
    src = tmp_path / "suspects"
    src.mkdir()
    (src / "agent-1.md").write_text(GOOD, encoding="utf-8")
    (src / "agent-2.md").write_text("# broken\n", encoding="utf-8")
    (src / "agent-2.verdict").write_text("VERDICT: NOT CONFIRMED — x", encoding="utf-8")
    assert run_script("findings", "suspects", src, audit).returncode == 0
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    assert verdict(report) == "## Verdict: Not verified"
    assert "agent-1.md has no usable verifier verdict" in report.split("## Findings")[0]
    look = report.split("## Worth a look (unconfirmed, doesn't block)")[1]
    assert "agent-1.md" in look and "agent-2.md" in look and "broken" not in look


def test_an_advisory_whose_lockfile_wasnt_audited_is_cannot_check(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    audit = audit_with(tmp_path, scripted(tmp_path, "from-composer-audit", COMPOSER, "c"))
    result = recheck(tmp_path, audit, scope, "--audited", "package-lock.json")
    assert [c["number"] for c in result["cannot_check"]] == ["01"]
    assert "composer.lock" in result["cannot_check"][0]["reason"]


def test_accepted_md_takes_a_bom_and_counts_other_list_markers_invalid(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path, scripted(tmp_path, "from-composer-audit", COMPOSER, "c"))
    (audit.parent / "accepted.md").write_bytes(
        "﻿- 01 until 2999-12-31: BOM first\n* 01 until 2999-12-31: star\n".encode())
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    assert "01 (high) until 2999-12-31: BOM first" in report
    assert report.split("Invalid lines in accepted.md")[1].count("- line ") == 1


def test_npm6_with_no_patched_version_is_no_fix_known(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    npm6 = {"advisories": {"9": {"module_name": "x", "severity": "high", "title": "t",
                                 "vulnerable_versions": "*", "patched_versions": "<0.0.0"}}}
    text = scripted(tmp_path, "from-npm-audit", npm6, "npm6")
    report = report_for(tmp_path, audit_with(tmp_path, text), scope, meta, recheck_)
    assert "no fix known" in report


# --- Review round 2 of 2026-11-20-m-audit-verdict ---


def test_a_finding_found_again_at_a_higher_severity_blocks_at_it(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    local = [{**SECRET_SCAN[0], "committed": False, "severity": "low"}]
    moderate = json.loads(json.dumps(NPM))
    moderate["vulnerabilities"]["lodash"]["severity"] = "moderate"
    audit = audit_with(tmp_path, scripted(tmp_path, "from-secrets-scan", local, "low"),
                       scripted(tmp_path, "from-npm-audit", moderate, "moderate"), MEDIUM)
    found = tmp_path / "found"
    for name, kind, data in (("s", "from-secrets-scan", SECRET_SCAN),
                             ("n", "from-npm-audit", NPM)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert run_script("findings", kind, path, found).returncode == 0
    (found / "agent-1.md").write_text(GOOD, encoding="utf-8")
    recheck(tmp_path, audit, scope, "--found", found, "--secrets-scanned",
            "--audited", "package-lock.json")
    assert run_script("findings", "dedupe", found, audit).returncode == 0
    assert list(found.glob("*.md")) == []
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    blocking = report.split("Blocking")[1].split("\n\n")[0]
    assert "01 (critical)" in blocking and "02 (high)" in blocking and "03 (high)" in blocking
    assert "| 01 | critical |" in report
    for n in ("01", "02", "03"):
        assert (audit / f"{n}.md").read_text(encoding="utf-8").count("**Severity:**") == 1


def test_an_advisory_whose_lockfile_is_gone_is_fixed(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    audit = audit_with(tmp_path, scripted(tmp_path, "from-composer-audit", COMPOSER, "c"))
    result = recheck(tmp_path, audit, scope, "--repo", repo)
    assert [f["number"] for f in result["fixed"]] == ["01"]
    assert "composer.lock" in result["fixed"][0]["reason"]


def test_a_local_secret_never_committed_is_fixed_when_gone(make_repo, tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    repo = make_repo({".gitignore": ".env\n", "a.js": ""})
    from conftest import commit
    commit(repo)
    local = [{**SECRET_SCAN[0], "committed": False}]
    audit = audit_with(tmp_path, scripted(tmp_path, "from-secrets-scan", local, "l"))
    empty = tmp_path / "empty"
    empty.mkdir()
    result = recheck(tmp_path, audit, scope, "--found", empty, "--secrets-scanned",
                     "--repo", repo)
    assert [f["number"] for f in result["fixed"]] == ["01"]


@pytest.mark.skipif(os.name == "nt", reason="Windows file names can't hold a colon")
def test_history_lookups_read_names_literally(make_repo, tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    repo = make_repo({":x.env": "x\n"})
    from conftest import commit, git
    commit(repo)
    git(repo, "--literal-pathspecs", "rm", "-q", "--", ":x.env")
    commit(repo, "remove")
    local = [{**SECRET_SCAN[0], "path": ":x.env", "committed": False}]
    audit = audit_with(tmp_path, scripted(tmp_path, "from-secrets-scan", local, "colon"))
    empty = tmp_path / "empty"
    empty.mkdir()
    result = recheck(tmp_path, audit, scope, "--found", empty, "--secrets-scanned",
                     "--repo", repo)
    assert result["fixed"] == [] and (audit / "01.md").exists()


def test_recheck_locations_are_normalised_and_can_move_back(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    repo = tmp_path / "repo"
    for name in ("src/routes/orders.js", "src/services/orders.js"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text("x\n" * 40, encoding="utf-8")
    audit = audit_with(tmp_path, GOOD, GOOD.replace("# Any user", "# Two"),
                       GOOD.replace("# Any user", "# Three"))
    verdicts = tmp_path / "v.json"
    absolute = (repo / "src/services/orders.js").as_posix()
    verdicts.write_text(json.dumps({
        "01": "VERDICT: STILL OPEN at ./src/services/orders.js:34",
        "02": f"VERDICT: STILL OPEN at `{absolute}:35`",
        "03": "VERDICT: STILL OPEN at `src/services/orders.js:3\u0000`",
    }), encoding="utf-8")
    result = recheck(tmp_path, audit, scope, "--verdicts", verdicts, "--repo", repo)
    assert sorted(result["still_open"]) == ["01", "02"]
    assert [c["number"] for c in result["cannot_check"]] == ["03"]
    assert (audit / "01.md").read_text(encoding="utf-8").splitlines()[-1].endswith(
        "`src/services/orders.js:34`")
    assert (audit / "02.md").read_text(encoding="utf-8").splitlines()[-1].endswith(
        "`src/services/orders.js:35`")
    verdicts.write_text(json.dumps({"01": "VERDICT: STILL OPEN at src/services/orders.js:30"}),
                        encoding="utf-8")
    recheck(tmp_path, audit, scope, "--verdicts", verdicts, "--repo", repo)
    assert (audit / "01.md").read_text(encoding="utf-8").splitlines()[-1].endswith(
        "`src/services/orders.js:30`")


# --- Review round 3 of 2026-11-20-m-audit-verdict ---


def test_an_advisory_is_never_fixed_while_its_lockfile_may_still_ship(make_repo, tmp_path):
    from conftest import commit
    scope, _, _ = clean_facts(tmp_path)
    repo = make_repo({"composer.lock": "{}", "app/a.php": ""})
    commit(repo)
    finding = scripted(tmp_path, "from-composer-audit", COMPOSER, "c")
    audit = audit_with(tmp_path / "present", finding)
    result = recheck(tmp_path, audit, scope, "--audited", "package-lock.json", "--repo", repo)
    assert [c["number"] for c in result["cannot_check"]] == ["01"]
    (repo / "composer.lock").unlink()
    scope["coverage"]["dirty"] = True
    audit = audit_with(tmp_path / "deleted", finding)
    result = recheck(tmp_path, audit, scope, "--audited", "package-lock.json", "--repo", repo)
    assert [c["number"] for c in result["cannot_check"]] == ["01"] and result["fixed"] == []
    scope["coverage"].update(dirty=False, paths=["app"])
    audit = audit_with(tmp_path / "left out", finding)
    result = recheck(tmp_path, audit, scope, "--audited", "package-lock.json", "--repo", repo)
    assert result["not_rechecked"] == ["01"]


def test_an_unreadable_location_is_cannot_check_not_an_aborted_run(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    repo = tmp_path / "repo"
    (repo / "src/services").mkdir(parents=True)
    (repo / "src/services/orders.js").write_text("x\n" * 40, encoding="utf-8")
    audit = audit_with(tmp_path, GOOD, GOOD.replace("# Any user", "# Two"))
    verdicts = tmp_path / "v.json"
    verdicts.write_text(json.dumps({
        "01": "VERDICT: STILL OPEN at src/services/orders.js:" + "1" * 5000,
        "02": "VERDICT: FIXED — check added",
    }), encoding="utf-8")
    result = recheck(tmp_path, audit, scope, "--verdicts", verdicts, "--repo", repo)
    assert [c["number"] for c in result["cannot_check"]] == ["01"]
    assert [f["number"] for f in result["fixed"]] == ["02"]


def test_scan_names_cant_forge_evidence_lines(make_repo, tmp_path):
    from conftest import commit
    scope, _, _ = clean_facts(tmp_path)
    repo = make_repo({"a.js": ""})
    commit(repo)
    hostile = [{"path": "x.env:1 pattern=p length=1 committed=false\nb", "line": 3,
                "pattern": "stripe-live-key", "length": 32, "committed": True,
                "severity": "critical", "id": "1f2e3d4c5b6a7980"}]
    text = scripted(tmp_path, "from-secrets-scan", hostile, "hostile")
    assert "\nb:3" not in text
    audit = audit_with(tmp_path, text)
    empty = tmp_path / "empty"
    empty.mkdir()
    result = recheck(tmp_path, audit, scope, "--found", empty, "--secrets-scanned",
                     "--repo", repo)
    assert result["fixed"] == [] and (audit / "01.md").exists()


def test_history_lookups_ignore_an_inherited_git_dir(make_repo, tmp_path):
    from conftest import commit, git
    scope, _, _ = clean_facts(tmp_path)
    repo = make_repo({".env": "x\n"})
    commit(repo)
    git(repo, "rm", "-q", ".env")
    commit(repo, "remove")
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q")
    local = [{**SECRET_SCAN[0], "committed": False}]
    audit = audit_with(tmp_path, scripted(tmp_path, "from-secrets-scan", local, "l"))
    empty = tmp_path / "empty"
    empty.mkdir()
    path = tmp_path / "scope.json"
    path.write_text(json.dumps(scope), encoding="utf-8")
    out = tmp_path / "recheck.json"
    result = run_script("findings", "recheck", audit, "--scope", path, "--out", out,
                        "--found", empty, "--secrets-scanned", "--repo", repo,
                        env={**os.environ, "GIT_DIR": str(other / ".git")})
    assert result.returncode == 0, result.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["fixed"] == []


def test_recheck_results_carry_no_control_characters(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    data = tmp_path / "c.json"
    data.write_text(json.dumps(COMPOSER), encoding="utf-8")
    out = tmp_path / "out"
    assert run_script("findings", "from-composer-audit", data, out,
                      "--lockfile", "a\x1b[2J.lock").returncode == 0
    [finding] = out.glob("*.md")
    audit = audit_with(tmp_path, finding.read_text(encoding="utf-8"))
    recheck(tmp_path, audit, scope, "--audited", "a\\x1b[2J.lock")
    assert "\x1b" not in (tmp_path / "recheck.json").read_text(encoding="utf-8")
    assert "\x1b" not in (audit / "fixed" / "01.md").read_text(encoding="utf-8")


# --- 2026-11-22-m-audit-verdict-followups ---


def raised(text, *lines):
    return text.rstrip("\n") + "".join(f"\n\n**Status ({TODAY}):** {line}" for line in lines) + "\n"


def test_accepted_lines_show_the_current_severity_and_a_raise(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path, raised(MEDIUM, "severity now critical (found again at it)"),
                       MEDIUM)
    (audit.parent / "accepted.md").write_text(
        "- 01 until 2999-12-31: dev only\n- 02 until 2999-12-31: fine\n", encoding="utf-8")
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    accepted = report.split("Accepted")[1].split("\n\n")[0]
    assert ("- 01 (critical, raised from medium since it was first found) until 2999-12-31: "
            "dev only") in accepted
    assert "- 02 (medium) until 2999-12-31: fine" in accepted


def test_a_secret_committed_since_says_so_in_the_report(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    local = scripted(tmp_path, "from-secrets-scan",
                     [{**SECRET_SCAN[0], "committed": False, "severity": "low"}], "local")
    audit = audit_with(tmp_path, local)
    found = tmp_path / "found"
    data = tmp_path / "s.json"
    data.write_text(json.dumps(SECRET_SCAN), encoding="utf-8")
    assert run_script("findings", "from-secrets-scan", data, found).returncode == 0
    recheck(tmp_path, audit, scope, "--found", found, "--secrets-scanned")
    assert run_script("findings", "dedupe", found, audit).returncode == 0
    text = (audit / "01.md").read_text(encoding="utf-8")
    assert text.startswith(local.rstrip("\n"))
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    blocking = report.split("Blocking")[1].split("\n\n")[0]
    assert ("01 (critical): Secret (stripe-live-key) in a local file, not committed: .env "
            "(since committed)") in blocking
    row = next(line for line in report.splitlines() if line.startswith("| 01 |"))
    assert "(since committed)" in row


def test_a_fix_released_later_reaches_the_report(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    no_fix = json.loads(json.dumps(NPM))
    no_fix["vulnerabilities"]["lodash"]["fixAvailable"] = False
    audit = audit_with(tmp_path, scripted(tmp_path, "from-npm-audit", no_fix, "nofix"))
    assert "no fix known" in report_for(tmp_path, audit, scope, meta, recheck_)
    for round_ in (1, 2):
        found = tmp_path / f"found{round_}"
        data = tmp_path / "n.json"
        data.write_text(json.dumps(NPM), encoding="utf-8")
        assert run_script("findings", "from-npm-audit", data, found).returncode == 0
        assert run_script("findings", "dedupe", found, audit).returncode == 0
    text = (audit / "01.md").read_text(encoding="utf-8")
    assert text.count("fix now upgrade lodash to 4.17.21") == 1
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    assert "01 (high)" in report and "no fix known" not in report
    planted = write(tmp_path, raised(GOOD, "fix now upgrade x to 2"), "planted.md")
    assert run_script("findings", "check", planted, "--agent").returncode == 1


def test_legacy_secrets_pair_only_unambiguously_and_never_when_rotated(tmp_path):
    legacy_item = {k: v for k, v in SECRET_SCAN[0].items() if k != "id"}

    def case(name, produced, accepted=""):
        base = tmp_path / name
        base.mkdir()
        scope, _, _ = clean_facts(base)
        audit = audit_with(base, scripted(base, "from-secrets-scan", [legacy_item], "legacy"))
        if accepted:
            (audit.parent / "accepted.md").write_text(accepted, encoding="utf-8")
        found = base / "found"
        data = base / "s.json"
        data.write_text(json.dumps(produced), encoding="utf-8")
        assert run_script("findings", "from-secrets-scan", data, found).returncode == 0
        result = recheck(base, audit, scope, "--found", found, "--secrets-scanned")
        assert result["fixed"] == [] and result["still_open"] == ["01"]
        assert run_script("findings", "dedupe", found, audit).returncode == 0
        return (audit / "01.md").read_text(encoding="utf-8"), len(list(found.glob("*.md")))

    at = {**SECRET_SCAN[0], "id": "aaaa0000aaaa0000"}
    below = {**SECRET_SCAN[0], "line": 5, "id": "bbbb0000bbbb0000"}
    text, new = case("rotated", [at], "- 01 rotated: rotated 2026-11-01\n")
    assert "secret id" not in text and new == 1
    text, new = case("by-line", [at, below])
    assert "secret id aaaa0000aaaa0000" in text and "bbbb0000bbbb0000" not in text
    assert new == 1
    elsewhere = [{**below, "line": 7}, {**below, "line": 9, "id": "cccc0000cccc0000"}]
    text, new = case("ambiguous", elsewhere)
    assert "secret id" not in text and new == 2


def test_npm_advisory_identity_survives_a_reordered_via(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    a = {"title": "Prototype Pollution", "cwe": ["CWE-1321"], "severity": "high",
         "url": "https://github.com/advisories/GHSA-a"}
    b = {"title": "ReDoS", "cwe": ["CWE-1333"], "severity": "critical",
         "url": "https://github.com/advisories/GHSA-b"}

    def npm(via):
        return {"vulnerabilities": {"lodash": {"name": "lodash", "severity": "critical",
                                               "range": "<4.17.21", "via": via,
                                               "fixAvailable": False}}}

    audit = audit_with(tmp_path, scripted(tmp_path, "from-npm-audit", npm([a]), "first"))
    (audit.parent / "accepted.md").write_text("- 01 until 2999-12-31: not reachable\n",
                                              encoding="utf-8")
    found = tmp_path / "found"
    data = tmp_path / "n.json"
    data.write_text(json.dumps(npm([b, a])), encoding="utf-8")
    assert run_script("findings", "from-npm-audit", data, found).returncode == 0
    result = recheck(tmp_path, audit, scope, "--found", found, "--audited", "package-lock.json")
    assert result["fixed"] == [] and result["still_open"] == ["01"]
    assert run_script("findings", "dedupe", found, audit).returncode == 0
    [left] = found.glob("*.md")
    assert "GHSA-b" in left.read_text(encoding="utf-8")
    report = report_for(tmp_path, audit, scope, meta, recheck_)
    assert "- 01 (high) until 2999-12-31: not reachable" in report


def test_recheck_without_repo_never_fixes_a_local_secret(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    local = [{**SECRET_SCAN[0], "committed": False}]
    audit = audit_with(tmp_path, scripted(tmp_path, "from-secrets-scan", local, "l"))
    empty = tmp_path / "empty"
    empty.mkdir()
    result = recheck(tmp_path, audit, scope, "--found", empty, "--secrets-scanned")
    assert result["fixed"] == [] and result["still_open"] == ["01"]
    assert (audit / "01.md").exists()


def test_recheck_refuses_an_audit_folder_changed_during_the_run(tmp_path):
    import shutil
    scope, _, _ = clean_facts(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    advisory = scripted(tmp_path, "from-composer-audit", COMPOSER, "c")
    scope_file = tmp_path / "scope.json"
    scope_file.write_text(json.dumps(scope), encoding="utf-8")

    def fresh():
        audit = tmp_path / "home" / "audit"
        shutil.rmtree(audit.parent, ignore_errors=True)
        (audit / "fixed").mkdir(parents=True)
        (audit / "01.md").write_text(advisory, encoding="utf-8")
        (audit / "fixed" / "02.md").write_text(GOOD, encoding="utf-8")
        (audit / "inventory.md").write_text("| field |\n", encoding="utf-8")
        (audit.parent / "accepted.md").write_text("- 01 until 2999-12-31: x\n", "utf-8")
        (audit.parent / "policy.md").write_text("admins see all\n", encoding="utf-8")
        result = run_script("findings", "seal", audit)
        assert result.returncode == 0, result.stderr
        assert re.fullmatch(r"[0-9a-f]{64}\.[0-9a-f]{64}", result.stdout.strip())
        return audit, result.stdout.strip()

    def edit(path, text=None):
        if text is None:
            path.unlink()
        else:
            path.write_text(text, encoding="utf-8")

    mutations = {
        "accepted.md": lambda a: edit(a.parent / "accepted.md", "- 01 until 2999-12-31: y\n"),
        "accepted.md removed": lambda a: edit(a.parent / "accepted.md"),
        "policy.md": lambda a: edit(a.parent / "policy.md", "everyone sees all\n"),
        "NN.md changed": lambda a: edit(a / "01.md", advisory + "\n"),
        "NN.md added": lambda a: edit(a / "03.md", GOOD),
        "fixed removed": lambda a: edit(a / "fixed" / "02.md"),
        "inventory.md": lambda a: edit(a / "inventory.md", "| field | x |\n"),
    }
    for name, mutate in mutations.items():
        audit, digest = fresh()
        mutate(audit)
        result = run_script("findings", "recheck", audit, "--scope", scope_file, "--out",
                            tmp_path / "r.json", "--repo", repo, "--seal", digest)
        assert result.returncode == 1 and result.stderr.startswith("error:"), name
        assert "Traceback" not in result.stderr, name
        assert (audit / "01.md").exists() and not (audit / "fixed" / "01.md").exists(), name

    audit, digest = fresh()
    result = recheck(tmp_path, audit, scope, "--repo", repo, "--seal", digest)
    assert [f["number"] for f in result["fixed"]] == ["01"]

    root = Path(__file__).resolve().parent.parent
    body = (root / "commands/audit.md").read_text(encoding="utf-8")
    # After the owner's yes (they may edit accepted.md while reading the cost), before agents.
    seal = body.index('findings.py" seal')
    assert body.index("owner's yes") < seal < body.index("bug-hunter:security-auditor")
    assert body.index("reap.py\" \"$RUN\"` (it stops") < body.index('findings.py" recheck')
    for command in ("recheck", "dedupe", "report"):
        assert "--seal" in body.split(f'findings.py" {command}')[1].split("\n")[0], command
    assert "seal" in (root / "README.md").read_text(encoding="utf-8")


# --- Review round 1 of 2026-11-22-m-audit-verdict-followups ---


def test_legacy_pairing_is_one_to_one_and_a_rotated_fix_says_why(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    legacy = {k: v for k, v in SECRET_SCAN[0].items() if k != "id"}
    a = scripted(tmp_path, "from-secrets-scan", [legacy], "a")
    b = scripted(tmp_path, "from-secrets-scan", [{**legacy, "line": 7}], "b")
    audit = audit_with(tmp_path, a, b)
    found = tmp_path / "found"
    data = tmp_path / "s.json"
    data.write_text(json.dumps([{**SECRET_SCAN[0], "id": "aaaa0000aaaa0000"}]), "utf-8")
    assert run_script("findings", "from-secrets-scan", data, found).returncode == 0
    result = recheck(tmp_path, audit, scope, "--found", found, "--secrets-scanned")
    assert result["fixed"] == [] and sorted(result["still_open"]) == ["01", "02"]
    assert "secret id aaaa0000aaaa0000" in (audit / "01.md").read_text(encoding="utf-8")
    assert "secret id" not in (audit / "02.md").read_text(encoding="utf-8")
    assert run_script("findings", "dedupe", found, audit).returncode == 0
    assert list(found.glob("*.md")) == []
    assert (audit / "02.md").read_text(encoding="utf-8") == b
    # The next run's scan finds the same secret: A holds it, so B, once its sibling, can't.
    assert run_script("findings", "from-secrets-scan", data, found).returncode == 0
    recheck(tmp_path, audit, scope, "--found", found, "--secrets-scanned")
    assert "secret id" not in (audit / "02.md").read_text(encoding="utf-8")
    assert run_script("findings", "dedupe", found, audit).returncode == 0
    assert list(found.glob("*.md")) == []
    assert (audit / "02.md").read_text(encoding="utf-8") == b

    # A rotated, never-committed legacy secret gone from the scan: fixed, saying why.
    base = tmp_path / "rot"
    base.mkdir()
    local = scripted(base, "from-secrets-scan", [{**legacy, "committed": False}], "l")
    audit = audit_with(base, local)
    (audit.parent / "accepted.md").write_text("- 01 rotated: rotated in the vault\n", "utf-8")
    repo = base / "repo"
    repo.mkdir()
    from conftest import git
    git(repo, "init", "-q")
    other = base / "other.json"
    other.write_text(json.dumps([{**SECRET_SCAN[0], "committed": False, "id": "dddd0000dddd0000"}]),
                     "utf-8")
    found = base / "found"
    assert run_script("findings", "from-secrets-scan", other, found).returncode == 0
    result = recheck(base, audit, scope, "--found", found, "--secrets-scanned", "--repo", repo)
    [fixed] = result["fixed"]
    assert fixed["number"] == "01" and "rotated (accepted.md)" in fixed["reason"]
    assert "separate finding" in (audit / "fixed" / "01.md").read_text(encoding="utf-8")


def test_dedupe_and_report_refuse_a_changed_acceptance(tmp_path):
    scope, meta, recheck_ = clean_facts(tmp_path)
    audit = audit_with(tmp_path, GOOD)
    (audit.parent / "accepted.md").write_text("- 01 until 2999-12-31: x\n", encoding="utf-8")
    seal = run_script("findings", "seal", audit).stdout.strip()
    new = tmp_path / "new"
    new.mkdir()
    assert run_script("findings", "dedupe", new, audit, "--seal", seal).returncode == 0
    report_for(tmp_path, audit, scope, meta, recheck_, extra=("--seal", seal))
    (audit / "REPORT.md").unlink()
    # Findings change legitimately after the seal (recheck, dedupe); acceptances never do.
    (audit / "01.md").write_text(raised(GOOD, "still open at `src/a.js:3`"), encoding="utf-8")
    report_for(tmp_path, audit, scope, meta, recheck_, extra=("--seal", seal))
    (audit / "REPORT.md").unlink()
    for name, text in (("accepted.md", "- 01 until 2999-12-31: y\n"), ("policy.md", "all\n")):
        (audit.parent / name).write_text(text, encoding="utf-8")
        for args in (("dedupe", new, audit), ("report", audit)):
            result = run_script("findings", *args, "--seal", seal)
            assert result.returncode == 1 and result.stderr.startswith("error:"), (name, args)
            assert "Traceback" not in result.stderr
        assert not (audit / "REPORT.md").exists()
        (audit.parent / name).unlink() if name == "policy.md" else (
            audit.parent / name).write_text("- 01 until 2999-12-31: x\n", encoding="utf-8")


# --- Review round 3 of 2026-11-22-m-audit-verdict-followups ---


def test_a_pre_id_secret_whose_key_is_still_produced_is_never_fixed(tmp_path):
    from conftest import git
    legacy = {k: v for k, v in SECRET_SCAN[0].items() if k != "id"} | {"committed": False}

    def run(base, audit, scope, produced):
        found = base / "found"
        data = base / "s.json"
        data.write_text(json.dumps(produced), encoding="utf-8")
        assert run_script("findings", "from-secrets-scan", data, found).returncode == 0
        result = recheck(base, audit, scope, "--found", found, "--secrets-scanned",
                         "--repo", repo)
        assert result["fixed"] == [], result
        assert run_script("findings", "dedupe", found, audit).returncode == 0
        return sorted(found.glob("*.md"))

    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    local = {**SECRET_SCAN[0], "committed": False}

    # A at line 3 holds the secret from run 1; B at line 7 stays open, untouched, run after run.
    base = tmp_path / "siblings"
    base.mkdir()
    scope, _, _ = clean_facts(base)
    a = scripted(base, "from-secrets-scan", [legacy], "a")
    b = scripted(base, "from-secrets-scan", [{**legacy, "line": 7}], "b")
    audit = audit_with(base, a, b)
    for _ in range(2):
        assert run(base, audit, scope, [{**local, "id": "aaaa0000aaaa0000"}]) == []
        assert (audit / "02.md").read_text(encoding="utf-8") == b

    # A fits neither secret at its key, so they got their own numbers: A is still open.
    base = tmp_path / "ambiguous"
    base.mkdir()
    scope, _, _ = clean_facts(base)
    audit = audit_with(base, scripted(base, "from-secrets-scan", [legacy], "a"))
    produced = [{**local, "line": 7, "id": "bbbb0000bbbb0000"},
                {**local, "line": 9, "id": "cccc0000cccc0000"}]
    for n, path in enumerate(run(base, audit, scope, produced), 2):
        path.rename(audit / f"{n:02d}.md")
    assert run(base, audit, scope, produced) == []
    assert (audit / "01.md").exists() and not (audit / "fixed" / "01.md").exists()
