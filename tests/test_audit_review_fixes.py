import json
import os
import shlex
import shutil
import sys
from pathlib import Path

import findings
from conftest import run_script
from test_audit_stack_coverage import OSV, SEMGREP, leads_scope, osv_findings, scope_with
from test_findings import (
    GOOD,
    audit_with,
    clean_facts,
    recheck,
    report_for,
    scripted,
)

ROOT = Path(__file__).resolve().parent.parent


def leads_dir(tmp_path):
    data = tmp_path / "semgrep.json"
    data.write_text(json.dumps(SEMGREP), encoding="utf-8")
    out = tmp_path / "leads"
    result = run_script("findings", "from-semgrep", data, out, "--scope", leads_scope(tmp_path))
    assert result.returncode == 0, result.stderr
    return out


def check_agent(tmp_path, text, leads=None):
    path = tmp_path / "finding.md"
    path.write_text(text, encoding="utf-8")
    args = ["--leads", leads] if leads else []
    return run_script("findings", "check", path, "--agent", *args)


ONE_SPOT = GOOD.replace("- `src/services/orders.js:30` (findById without owner filter)\n", "")


def test_a_lead_named_by_rule_id_or_disguised_word_needs_a_trace(tmp_path):
    leads = leads_dir(tmp_path)
    for mention in ("Rule python.lang.security.audit.formatted-sql-query fired.",
                    "Flagged by ｓemgrep.", "Flagged by sem​grep."):
        text = ONE_SPOT.replace("## Impact\n", f"## Impact\n{mention}\n")
        result = check_agent(tmp_path, text, leads)
        assert result.returncode == 1 and "lead" in result.stdout.lower(), mention
    assert check_agent(tmp_path, ONE_SPOT, leads).returncode == 0
    # A word a rule is named after isn't a citation of that rule.
    words = ONE_SPOT.replace("## Impact\n",
                             "## Impact\nAn open-redirect and a formatted-sql-query.\n")
    assert check_agent(tmp_path, words, leads).returncode == 0


def test_a_finding_at_a_lead_spot_needs_a_second_spot(tmp_path):
    leads = leads_dir(tmp_path)
    at_lead = ONE_SPOT.replace("src/routes/orders.js:12", "src/routes/orders.py:12")
    assert check_agent(tmp_path, at_lead, leads).returncode == 1
    bare_extra = ONE_SPOT.replace("(GET /orders/:id)", "x:1 y:2").replace(
        "## Impact\n", "## Impact\nFrom semgrep.\n")
    assert check_agent(tmp_path, bare_extra, leads).returncode == 1


def test_osv_conversion_refuses_a_failed_run(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text('{"results": []}', encoding="utf-8")
    for code, ok in (("127", False), ("128", False), ("0", True), ("1", True)):
        result = run_script("findings", "from-osv-scanner", path, tmp_path / "o",
                            "--lockfile", "package-lock.json", "--exit", code)
        assert (result.returncode == 0) is ok, (code, result.stderr)
        if not ok:
            assert result.stderr.startswith("error:") and code in result.stderr


def osv_one(severity=None, ids=("GHSA-aaaa-bbbb-cccc",), groups=None, version="1.0.0",
            ranges=None):
    vuln = {"id": ids[0], "aliases": list(ids[1:]), "summary": "bad"}
    if severity:
        vuln["database_specific"] = {"severity": severity}
    if ranges:
        vuln["affected"] = [{"package": {"name": "pkg"}, "ranges": ranges}]
    entry = {"package": {"name": "pkg", "version": version, "ecosystem": "npm"},
             "vulnerabilities": [vuln], "groups": [{"ids": list(ids)}]}
    if groups:
        entry["dependency_groups"] = groups
    return {"results": [{"packages": [entry]}]}


def severity_of(tmp_path, data, name):
    result, files = osv_findings(tmp_path, data, name)
    assert result.returncode == 0, result.stderr
    [found] = files
    return findings._parse(found.read_text(encoding="utf-8"))[0]["Severity"]


def test_malicious_and_unrated_advisories_block(tmp_path):
    assert severity_of(tmp_path, osv_one(ids=("MAL-2024-1234",)), "mal") == "critical"
    assert severity_of(tmp_path, osv_one(), "unrated") == "high"
    two = osv_one(severity="LOW", ids=("GHSA-aaaa-bbbb-cccc", "GHSA-dddd-eeee-ffff"))
    pkg = two["results"][0]["packages"][0]
    pkg["vulnerabilities"] = [
        {"id": "GHSA-aaaa-bbbb-cccc", "database_specific": {"severity": "LOW"}},
        {"id": "GHSA-dddd-eeee-ffff", "database_specific": {"severity": "CRITICAL"}}]
    assert severity_of(tmp_path, two, "worst") == "critical"


def test_dev_optional_packages_still_count(tmp_path):
    result, files = osv_findings(tmp_path, osv_one(groups=["dev", "optional"]), "devopt")
    assert result.returncode == 0 and len(files) == 1, result.stderr


def test_fix_version_is_above_the_installed_one(tmp_path):
    ranges = [{"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "3.2.20"}]},
              {"type": "SEMVER", "events": [{"introduced": "4.0.0"}, {"fixed": "4.1.8"}]},
              {"type": "GIT", "events": [{"introduced": "0"}, {"fixed": "abc123def"}]}]
    result, files = osv_findings(tmp_path, osv_one(version="4.1.5", ranges=ranges), "fix")
    assert result.returncode == 0, result.stderr
    text = files[0].read_text(encoding="utf-8")
    assert "upgrade pkg to 4.1.8" in text and "3.2.20" not in text and "abc123" not in text
    for installed, fixed, expected in (("4.1.5-rc.1", "4.1.5", "4.1.5"),
                                       ("2.0.0rc1", "2.0.0", "2.0.0"),
                                       ("v1.2.3", "v1.2.4", "v1.2.4")):
        ranges = [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": fixed}]}]
        name = installed.replace(".", "_")
        result, files = osv_findings(tmp_path, osv_one(version=installed, ranges=ranges), name)
        assert result.returncode == 0, result.stderr
        assert f"upgrade pkg to {expected}" in files[0].read_text(encoding="utf-8"), installed


def test_an_id_less_finding_stays_open_while_osv_reports_its_package(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    old = scripted(tmp_path, "from-npm-audit", {"vulnerabilities": {"lodash": {
        "name": "lodash", "severity": "high", "range": "<4.17.21",
        "via": [{"title": "Prototype Pollution", "url": "https://npmjs.com/advisories/1523",
                 "range": "<4.17.21"}], "fixAvailable": True}}}, "npm6")
    audit = audit_with(tmp_path, old)
    found = tmp_path / "found"
    path = tmp_path / "osv.json"
    path.write_text(json.dumps(OSV), encoding="utf-8")
    assert run_script("findings", "from-osv-scanner", path, found, "--lockfile",
                      "package-lock.json", "--exit", "1").returncode == 0
    result = recheck(tmp_path, audit, scope, "--found", found, "--audited", "package-lock.json")
    assert "01" in result["still_open"], result


def test_advisory_ids_are_matched_exactly():
    text = ("https://github.com/FriendsOfPHP/security-advisories/blob/master/go-kit/mal-x.yaml "
            "GHSA-abcd-efgh-ijkl CVE-2021-44228 GO-2023-1234 MAL-2024-99 PYSEC-2021-5 "
            "RUSTSEC-2020-0001 PKSA-1234-abcd-5678")
    ids = set(findings.ADVISORY_ID.findall(text))
    assert ids == {"GHSA-abcd-efgh-ijkl", "CVE-2021-44228", "GO-2023-1234", "MAL-2024-99",
                   "PYSEC-2021-5", "RUSTSEC-2020-0001", "PKSA-1234-abcd-5678"}, ids


def test_error_lines_escape_the_targets_text(tmp_path):
    data = {"results": [{"packages": [{"package": {"name": "x\nerror: forged"},
                                       "vulnerabilities": "nope"}]}]}
    result, _ = osv_findings(tmp_path, data, "forged")
    assert result.returncode == 1
    assert result.stderr.count("\n") == 1 and result.stderr.startswith("error:"), result.stderr


def test_scope_emits_the_semgrep_and_offline_steps(make_repo, tmp_path):
    repo = make_repo({"api/auth.py": "", "api/$(touch pwned).py": "", "-config=x.py": "",
                      "web/package-lock.json": "", "svc/go.sum": "", "svc/go.mod": "",
                      "svc/main.go": ""})
    scope = scope_with(repo, tmp_path, ("osv-scanner", "semgrep"))
    step = scope["semgrep"]["step"]
    assert "--metrics=off" in step and "p/python" in step and "p/golang" in step
    assert "p/owasp-top-ten" in step and step.endswith(" .")
    assert "pwned" not in step and "x.py" not in step
    for audit in scope["audits"]:
        words = shlex.split(audit["step_offline"].split("&&")[-1].strip(" ()"))
        config = Path(words[words.index("--config") + 1])
        assert config.is_file() and config.read_text(encoding="utf-8") == ""
        assert "--offline-vulnerabilities" in audit["step_offline"]
        assert "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY=" in audit["step_offline"]
        assert "--offline" not in audit["step"]
    go = next(a for a in scope["audits"] if a["lockfile"] == "svc/go.sum")
    assert "--lockfile go.mod" in go["step"]


def test_scope_ignores_a_tool_planted_in_the_repo(make_repo, tmp_path):
    repo = make_repo({"src/app.py": ""})
    planted = repo / ("osv-scanner.bat" if os.name == "nt" else "osv-scanner")
    planted.write_text("@echo off\r\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")
    planted.chmod(0o755)
    keep = dict.fromkeys(str(Path(p).parent) for p in (sys.executable, shutil.which("git")))
    env = dict(os.environ, PATH=os.pathsep.join(keep))
    env.pop("NoDefaultCurrentDirectoryInExePath", None)
    result = run_script("scope", repo, "--focus", "security", cwd=repo, env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["tools"]["osv-scanner"]["found"] is False


def test_missing_leads_run_reads_as_not_run(tmp_path):
    scope, meta, check = clean_facts(tmp_path)
    meta.pop("leads_run", None)
    report = report_for(tmp_path, audit_with(tmp_path), scope, meta, check)
    assert "Semgrep leads not run" in report


def test_audit_command_runs_only_scripted_steps():
    text = (ROOT / "commands" / "audit.md").read_text(encoding="utf-8")
    after_yes = text.split("Start the audit?")[1]
    for words in ("step_offline", "--exit", "--leads", "`semgrep` `step`"):
        assert words in after_yes, words
    assert "every part's files" not in after_yes
    assert "add `--offline" not in text


def test_a_fixed_advisory_moves_to_fixed_while_its_package_has_another(tmp_path):
    scope, _, _ = clean_facts(tmp_path)
    old = scripted(tmp_path, "from-npm-audit", {"vulnerabilities": {"pkg": {
        "name": "pkg", "severity": "high", "range": "<2",
        "via": [{"title": "old bug", "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc",
                 "range": "<2"}], "fixAvailable": True}}}, "old")
    audit = audit_with(tmp_path, old)
    found = tmp_path / "found"
    path = tmp_path / "osv.json"
    path.write_text(json.dumps(osv_one(severity="LOW", ids=("GHSA-dddd-eeee-ffff",))),
                    encoding="utf-8")
    assert run_script("findings", "from-osv-scanner", path, found, "--lockfile",
                      "package-lock.json", "--exit", "1").returncode == 0
    result = recheck(tmp_path, audit, scope, "--found", found, "--audited", "package-lock.json")
    assert [f["number"] for f in result["fixed"]] == ["01"], result


def test_odd_osv_shapes(tmp_path):
    result, files = osv_findings(tmp_path, {"results": [{"packages": None}]}, "null")
    assert result.returncode == 0 and files == [], result.stderr
    no_groups = osv_one(severity="CRITICAL")
    del no_groups["results"][0]["packages"][0]["groups"]
    assert severity_of(tmp_path, no_groups, "nogroups") == "critical"
    orphan = osv_one(severity="LOW")
    orphan["results"][0]["packages"][0]["groups"].append({"ids": ["GHSA-zzzz-yyyy-xxxx"]})
    result, files = osv_findings(tmp_path, orphan, "orphan")
    texts = [f.read_text(encoding="utf-8") for f in files]
    lone = next(t for t in texts if "GHSA-zzzz-yyyy-xxxx" in t)
    assert "**Severity:** high" in lone and "GHSA-aaaa-bbbb-cccc" not in lone
