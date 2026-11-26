"""Audit findings: format check, audit folder, converters from script output, and the report."""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath

from drafts import drafts_dir, fenced, numbered, title
from secrets_scan import (
    PATTERNS,
    SEVERITY_RANK,
    counts,
    in_history,
    is_placeholder,
    known_secret_in,
    load_prints,
)

SEVERITIES = ["critical", "high", "medium", "low"]
CATEGORIES = ["authz", "injection", "secrets", "session", "pii-logged", "pii-exposed",
              "pii-third-party", "pii-storage", "pii-retention", "dependency", "config"]
PROOFS = ["proven", "traced", "advisory"]
SECTIONS = ["Where", "Evidence", "Impact", "Fix"]
FIELD = re.compile(r"^\*\*(Severity|Category|CWE|Proof):\*\*\s*(.*?)\s*$")
PATH_LINE = re.compile(r"[^\s`'\"()]+:\d+")
QUOTED_PATH_LINE = re.compile(r"`([^`]+:\d+)[^`]*`")
# Advisory ids across databases: one vulnerability is GHSA in npm, PKSA plus CVE in composer and
# GHSA plus CVE in OSV, so a finding is known by every id it names.
# Each database's own id format, case-sensitive: a word in a URL path (`/go-kit/`) is no id.
ADVISORY_ID = re.compile(r"(?<![\w-])(?:GHSA(?:-[0-9a-z]+)+|CVE-\d{4}-\d{4,}"
                         r"|PKSA(?:-[0-9a-z]{4}){3}|(?:PYSEC|GO|OSV|GMS|MAL|RUBYSEC)-\d{4}-\d+|RUSTSEC-\d{4}-\d{4})"
                         r"(?![\w-])")
OSV_SOURCE = "source: osv-scanner"
NPM_THROUGH = "see npm audit"
SEMGREP = re.compile(r"semgrep")
LEAD_LINE = re.compile(r"^semgrep (\S+) (.+?):(\d+) ")
ERROR_MAX = 300
LEAD_MAX = 500
LEADS_PER_PART = 50
NPM_SEVERITY = {"critical": "critical", "high": "high", "moderate": "medium", "medium": "medium",
                "low": "low", "info": "low"}
INVENTORY_COLUMNS = ["field", "defined", "logged", "returned", "sent to", "stored", "deletion"]
HERE = Path(__file__).resolve().parent
CHECKLIST_DIR = HERE.parent / "security"
_OWASP = json.loads((HERE / "owasp.json").read_text(encoding="utf-8"))["categories"]
OWASP_TITLES = {cat: data["title"] for cat, data in _OWASP.items()}
OWASP_OF = {cwe: cat for cat, data in _OWASP.items() for cwe in data["cwes"]}
SECRET_EVIDENCE = re.compile(
    r"^(?P<path>.+):(?P<line>[0-9]+) pattern=(?P<pattern>\S+) length=(?P<length>\S+) "
    r"committed=(?P<committed>true|false)(?: id=(?P<id>[0-9a-f]{8,64}))?\s*$", re.M)
STATUS = re.compile(r"^\*\*Status \([0-9]{4}-[0-9]{2}-[0-9]{2}\):\*\* still open at "
                    r"`([^`]+:[0-9]+)`\s*$", re.M)
ACCEPT = re.compile(r"-[ \t]+([0-9]{1,4})[ \t]+(?:until[ \t]+([0-9]{4}-[0-9]{2}-[0-9]{2})"
                    r"|(rotated))[ \t]*:[ \t]*(\S.*)")
STILL_OPEN = re.compile(r"VERDICT: STILL OPEN at (?:`([^`]+:[0-9]+)`|(\S+:[0-9]+))\.?\s*")
FIXED = re.compile(r"VERDICT: FIXED\s*[—–-]+\s*(\S.*)")
CANNOT_CHECK = re.compile(r"VERDICT: CANNOT CHECK\b\s*(?:[—–-]+\s*(.*))?")
SEVERITY_NOW = re.compile(r"^\*\*Status \([0-9]{4}-[0-9]{2}-[0-9]{2}\):\*\* severity now "
                          r"(critical|high|medium|low)\b", re.M)
SCAN_MARK = re.compile(r"^\$ python3 scripts/secrets_scan\.py", re.M)
SECRET_ID = re.compile(
    r"^\*\*Status \([0-9]{4}-[0-9]{2}-[0-9]{2}\):\*\* secret id ([0-9a-f]{8,64})\s*$", re.M)
SECRET_ID_IN_EVIDENCE = re.compile(r" committed=(?:true|false) id=([0-9a-f]{8,64})\s*$", re.M)
SEEN_COMMITTED = re.compile(r"^\*\*Status \([0-9]{4}-[0-9]{2}-[0-9]{2}\):\*\* seen committed\s*$",
                            re.M)
FIX_NOW = re.compile(r"^\*\*Status \([0-9]{4}-[0-9]{2}-[0-9]{2}\):\*\* fix now (\S.*?)\s*$", re.M)
REJECTED = ".unconfirmed-refused.json"
SCRIPT_ONLY = [
    (re.compile(r"^\*\*Proof:\*\*\s*advisory\s*$", re.M),
     "Proof: advisory: only the dependency audit writes advisories"),
    (re.compile(r"\$ python3 scripts/secrets_scan\.py"),
     "secrets scan output: only the scan writes it"),
    (re.compile(r"^\*\*(?:Status|Fixed) \(", re.M),
     "a Status or Fixed line: only recheck writes those"),
    (re.compile(r"^Verifier:", re.M), "a Verifier line: only suspects writes those"),
    (re.compile(r"^\s*Mode:\s*re-check\s*$", re.M | re.I),
     "a Mode: re-check line: only the re-check prompt has one"),
]
UNCONFIRMED = re.compile(r"VERDICT: (?:NOT CONFIRMED|CANNOT CHECK)\b.*")
NO_FIX = ("no fix released yet", "see the advisory")
# Where a version label ranks against its release (4); an unknown label counts as a pre-release.
PRE_RELEASE = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "c": 3, "rc": 3, "pre": 3,
               "preview": 3, "post": 5, "p": 5, "pl": 5, "patch": 5}


class _Malformed(Exception):
    pass


# Findings quote code, so shape-guessing (`NAME = value`) can't tell a secret from code. The
# check uses the vendor-shaped patterns, which code doesn't match, and the fingerprints of the
# secrets the scan actually found.
CHECK_PATTERNS = [p for p in PATTERNS if not p.get("env_only")]
# A long base64 line with both cases is a key body even when the scan never saw that key.
KEY_BODY = re.compile(r"^\s*(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[a-z])"
                      r"[A-Za-z0-9+/]{60,}={0,2}\s*$", re.M)
PRINTS: dict = {}


def _secret_hits(text: str) -> list[str]:
    hits = []
    for pattern in CHECK_PATTERNS:
        for match in pattern["compiled"].finditer(text):
            value = match.groupdict().get("value") or match.group(0)
            if counts(pattern, value) and not is_placeholder(value):
                hits.append(pattern["name"])
                break
    if KEY_BODY.search(text):
        hits.append("key-body")
    if PRINTS and known_secret_in(text, PRINTS):
        hits.append("a secret found in this repo")
    return hits


def _scrub(text: str) -> str:
    """Withhold any line that looks like it holds a secret; output must never carry one."""
    return "\n".join(
        "(withheld: this line looked like it held a secret)" if _secret_hits(line) else line
        for line in text.split("\n")
    )


def _parse(text: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """A finding's header fields and its sections' lines (headings inside code blocks ignored)."""
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current = None
    for line, fence in fenced(text.splitlines()):
        if not fence and line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
        elif match := FIELD.match(line):
            fields[match[1]] = match[2]
    return fields, sections


def _problems(text: str) -> list[str]:
    """Every way a finding breaks the format; empty when it's good."""
    found = []
    first = next((line for line in text.splitlines() if line.strip()), "")
    if not first.startswith("# ") or not first[2:].strip():
        found.append("missing a '# ' title line")
    fields, sections = _parse(text)
    for name, allowed in (("Severity", SEVERITIES), ("Category", CATEGORIES), ("Proof", PROOFS)):
        if fields.get(name) not in allowed:
            found.append(f"{name} must be one of: {', '.join(allowed)}")
    if not re.fullmatch(r"CWE-\d+", fields.get("CWE", "")):
        found.append("CWE must look like CWE-<n>")
    for section in SECTIONS:
        if section not in sections:
            found.append(f"missing section: ## {section}")
        elif not any(line.strip() for line in sections[section]):
            found.append(f"empty section: ## {section}")
    if "Where" in sections and not any(PATH_LINE.search(line) for line in sections["Where"]):
        found.append("## Where has no path:line")
    evidence = sections.get("Evidence", [])
    if evidence and not any(fence for _, fence in fenced(evidence)):
        found.append("## Evidence has no code block")
    for name in _secret_hits(text):
        found.append(f"contains what looks like a secret ({name}); write <redacted> instead")
    return found


def _write_private(path: Path, text: str | bytes) -> None:
    """Write atomically with mode 0600: audit output describes vulnerabilities."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".findings-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(text if isinstance(text, bytes) else text.encode("utf-8"))
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


ESCAPES = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _printable(value: object) -> str:
    """Text with every control character escaped, so a name can't add a line or reach a terminal."""
    return "".join(c if c.isprintable() else ESCAPES.get(c) or (
        f"\\x{ord(c):02x}" if ord(c) < 0x100 else f"\\u{ord(c):04x}") for c in str(value))


def _render(head: str, severity: str, category: str, cwe: str, proof: str, where: list[str],
           evidence: str, impact: str, fix: str) -> str:
    return (
        f"# {head}\n\n**Severity:** {severity}\n**Category:** {category}\n**CWE:** {cwe}\n"
        f"**Proof:** {proof}\n\n## Where\n" + "".join(f"- {w}\n" for w in where)
        + f"\n## Evidence\n```\n{evidence}\n```\n\n## Impact\n{impact}\n\n## Fix\n{fix}\n"
    )


def _save(out: Path, prefix: str, findings: list[str]) -> None:
    taken = {p.name for p in out.glob(f"{prefix}-*.md")} if out.is_dir() else set()
    n = 0
    for text in findings:
        n += 1
        while f"{prefix}-{n:03d}.md" in taken:
            n += 1
        _write_private(out / f"{prefix}-{n:03d}.md", text)


def _load(path: str) -> object:
    try:
        if path == "-":
            return json.loads(sys.stdin.read())
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise _Malformed(f"can't read {path} as JSON: {type(exc).__name__}") from exc


def _from_secrets_scan(data: object) -> list[str]:
    if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
        raise _Malformed("secrets scan output must be a JSON list of findings")
    found = []
    for item in data:
        try:
            # Names come from the target's files: escaped, so one can't forge an evidence line.
            path, line = _printable(item["path"]), int(item["line"])
            name = _printable(item["pattern"])
            severity, committed = item["severity"], bool(item["committed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise _Malformed(f"secrets scan finding without {exc}") from exc
        if severity not in SEVERITIES:
            raise _Malformed(f"secrets scan severity {severity!r} isn't one of {SEVERITIES}")
        where = ("in a local file whose path is in git history" if item.get("history") is True
                 else "committed to the repository" if committed
                 else "in a local file, maybe committed before (git couldn't say)"
                 if item.get("history_unknown") is True
                 else "in a local file, not committed")
        ident = item.get("id")
        ident = f" id={ident}" if isinstance(ident, str) and re.fullmatch(
            r"[0-9a-f]{8,64}", ident) else ""
        found.append(_render(
            f"Secret ({name}) {where}: {path}", severity, "secrets", "CWE-798", "proven",
            [f"`{path}:{line}`"],
            f"$ python3 scripts/secrets_scan.py <repo>\n{path}:{line} pattern={name} "
            f"length={item.get('length', '?')} committed={str(committed).lower()}{ident}",
            "Anyone with read access to the repository or its history can use this credential."
            if committed else
            "Maybe in git history already (git couldn't say); if not, it's one `git add -A` "
            "from being committed." if item.get("history_unknown") is True else
            "Only on this machine for now, but it's one `git add -A` from being committed.",
            "Rotate the credential, remove it (and from git history if committed), and load it "
            "from the environment or a secret manager.",
        ))
    return found


def _npm_finding(name: str, severity: str, title_text: str, cwe: str, advisory: str,
                 affected: str, fix: str, lockfile: str, source: str = "") -> str:
    name, title_text, advisory, affected, fix, lockfile = map(
        _printable, (name, title_text, advisory, affected, fix, lockfile))
    return _render(
        f"Vulnerable dependency {name}: {title_text}", severity, "dependency", cwe, "advisory",
        [f"`{lockfile}:1` ({name} {affected})"],
        f"advisory: {advisory}\npackage: {name}\naffected: {affected}\nfix: {fix}"
        + (f"\n{source}" if source else ""),
        f"The deployed app includes {name} {affected}, which has a published advisory "
        f"({title_text}).",
        f"{fix[:1].upper()}{fix[1:]}, then re-run the audit.",
    )


def _fix_text(package: str, fix: object) -> str:
    if isinstance(fix, dict) and "version" in fix:
        target = fix.get("name", package)
        return f"upgrade {target} to {fix['version']}" + (
            f" (it brings in a fixed {package})" if target != package else "")
    return "run npm audit fix" if fix else "no fix released yet"


def _from_npm_audit(data: object, lockfile: str = "package-lock.json") -> list[str]:
    if not isinstance(data, dict):
        raise _Malformed("npm audit output must be a JSON object")
    if isinstance(data.get("error"), dict):
        err = data["error"]
        summary = (str(err.get("summary") or "").splitlines() or [""])[0]
        raise _Malformed(f"npm audit failed: {err.get('code', '?')}: {summary}")
    if "vulnerabilities" not in data and "advisories" not in data:
        raise _Malformed("npm output has no audit result (no vulnerabilities or advisories)")
    found = []
    for name, vuln in (data.get("vulnerabilities") or {}).items():
        if not isinstance(vuln, dict):
            raise _Malformed(f"npm audit entry for {name} isn't an object")
        # One finding per advisory: which one npm lists first changes from run to run, and
        # each is what an earlier finding and its acceptance are matched by.
        via = [v for v in vuln.get("via", []) if isinstance(v, dict)] or [{}]
        severity = NPM_SEVERITY.get(vuln.get("severity"), "medium")
        fix = vuln.get("fixAvailable")
        for advisory in via:
            cwes = advisory.get("cwe") or []
            found.append(_npm_finding(
                str(vuln.get("name", name)), NPM_SEVERITY.get(advisory.get("severity"), severity),
                str(advisory.get("title")
                    or f"through {', '.join(map(str, vuln.get('via', [])))}"),
                cwes[0] if isinstance(cwes, list) and cwes else "CWE-1395",
                str(advisory.get("url") or advisory.get("source") or NPM_THROUGH),
                str(vuln.get("range", "?")), _fix_text(str(vuln.get("name", name)), fix),
                lockfile))
    for key, adv in (data.get("advisories") or {}).items():
        if not isinstance(adv, dict):
            raise _Malformed(f"npm audit advisory {key} isn't an object")
        cwe = adv.get("cwe")
        cwe = cwe[0] if isinstance(cwe, list) and cwe else cwe
        found.append(_npm_finding(
            str(adv.get("module_name", key)), NPM_SEVERITY.get(adv.get("severity"), "medium"),
            str(adv.get("title", "advisory")),
            cwe if isinstance(cwe, str) and re.fullmatch(r"CWE-\d+", cwe) else "CWE-1395",
            str(adv.get("url") or adv.get("id") or key), str(adv.get("vulnerable_versions", "?")),
            # npm 6 writes <0.0.0 when no version is patched.
            f"upgrade to {adv['patched_versions']}"
            if adv.get("patched_versions") not in (None, "", "<0.0.0")
            else "no fix released yet", lockfile))
    return found


def _from_composer_audit(data: object, lockfile: str = "composer.lock") -> list[str]:
    if not isinstance(data, dict):
        raise _Malformed("composer audit output must be a JSON object")
    if "advisories" not in data:
        raise _Malformed("composer output has no audit result (no advisories key)")
    advisories = data["advisories"] or {}
    if not isinstance(advisories, dict):
        raise _Malformed("composer audit advisories must be an object")
    found = []
    for package, items in advisories.items():
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise _Malformed(f"composer audit entry for {package} isn't a list of advisories")
        for adv in items:
            found.append(_npm_finding(
                package, NPM_SEVERITY.get(str(adv.get("severity")).lower(), "medium"),
                str(adv.get("title", "advisory")), "CWE-1395",
                " ".join(str(adv[k]) for k in ("advisoryId", "cve", "link") if adv.get(k)),
                str(adv.get("affectedVersions", "?")), "see the advisory", lockfile))
    return found


def _osv_severity(vulns: list[dict], group: dict, ids: list[str]) -> str:
    """The worst rating any member or the group's score gives; a malicious package is critical.

    An unrated advisory is high, so it blocks until someone reads it: many PYSEC, GO and
    RUSTSEC records carry no rating at all.
    """
    if any(i.upper().startswith("MAL-") for i in ids):
        return "critical"
    rated = [NPM_SEVERITY[r] for r in (str((v.get("database_specific") or {}).get(
        "severity", "")).lower() for v in vulns) if r in NPM_SEVERITY]
    try:
        score = float(group.get("max_severity", ""))
        rated.append("critical" if score >= 9 else "high" if score >= 7 else
                     "medium" if score >= 4 else "low")
    except (TypeError, ValueError):
        pass
    return min(rated, key=SEVERITIES.index) if rated else "high"


def _osv_fix(vulns: list[dict], package: str, installed: str) -> str:
    """The lowest fixed version above the installed one; GIT ranges fix commits, not versions."""
    fixed = []
    for vuln in vulns:
        for affected in vuln.get("affected") or []:
            if not isinstance(affected, dict) or (
                    (affected.get("package") or {}).get("name") not in (None, package)):
                continue
            for span in affected.get("ranges") or []:
                if not isinstance(span, dict) or span.get("type") == "GIT":
                    continue
                for event in span.get("events") or []:
                    if isinstance(event, dict) and isinstance(event.get("fixed"), str):
                        fixed.append(event["fixed"])
    if re.match(r"v?\d", installed):
        fixed = [v for v in fixed if _version_key(v) > _version_key(installed)]
    return f"upgrade {package} to {min(fixed, key=_version_key)}" if fixed else NO_FIX[0]


def _version_key(version: str) -> tuple:
    """Release numbers, then dev < alpha < beta < rc < the release < a post or patch release."""
    found = re.match(r"v?(\d+(?:\.\d+)*)[.\-_]?(.*)", version)
    if not found:
        return ((), 0, [(1, version)])
    release = tuple(int(n) for n in found[1].split("."))
    parts = [p for p in re.split(r"[.\-_]|(?<=\d)(?=\D)|(?<=\D)(?=\d)",
                                 found[2].split("+", 1)[0].lower()) if p]
    label = next((p for p in parts if not p.isdigit()), None)
    stage = (PRE_RELEASE.get(label, 3) if label else 4) if parts else 4
    return (release, stage, [(0, int(p)) if p.isdigit() else (1, p) for p in parts])


def _from_osv_scanner(data: object, lockfile: str) -> list[str]:
    """One advisory finding per (package, vulnerability group) OSV-Scanner reports.

    A package the lockfile marks dev-only is skipped, as npm audit --omit=dev did.
    """
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise _Malformed("OSV-Scanner output must be an object with a results list")
    found = []
    for result in data["results"]:
        if not isinstance(result, dict) or not isinstance(result.get("packages") or [], list):
            raise _Malformed("an OSV-Scanner result must be an object with a packages list")
        for entry in result.get("packages") or []:
            package = entry.get("package") if isinstance(entry, dict) else None
            if not isinstance(package, dict) or not isinstance(package.get("name"), str):
                raise _Malformed("an OSV-Scanner package must name its package")
            # Only when every group is dev: npm's devOptional comes as ["dev", "optional"].
            groups_of = entry.get("dependency_groups") or []
            if isinstance(groups_of, list) and groups_of and set(groups_of) == {"dev"}:
                continue
            vulns = entry.get("vulnerabilities") or []
            if not isinstance(vulns, list) or not all(isinstance(v, dict) for v in vulns):
                raise _Malformed(f"OSV-Scanner vulnerabilities for {package['name']} must be "
                                 "a list of objects")
            groups = [g for g in entry.get("groups") or [] if isinstance(g, dict)
                      and isinstance(g.get("ids"), list)] or [
                {"ids": [v.get("id"), *(v.get("aliases") or [])]} for v in vulns]
            for group in groups:
                ids = [str(i) for i in group["ids"] if isinstance(i, str)]
                members = [v for v in vulns if v.get("id") in ids
                           or set(v.get("aliases") or []) & set(ids)]
                for v in members:
                    ids += [str(a) for a in v.get("aliases") or [] if isinstance(a, str)]
                ids = list(dict.fromkeys(ids))
                if not ids:
                    continue
                ghsa = next((i for i in ids if i.upper().startswith("GHSA-")), None)
                head = (f"https://github.com/advisories/{ghsa}" if ghsa
                        else f"https://osv.dev/vulnerability/{ids[0]}")
                advisory = " ".join([head, *(i for i in ids if i != ghsa)])
                primary = members[0] if members else {}
                cwes = (primary.get("database_specific") or {}).get("cwe_ids") or []
                cwe = next((c for c in cwes if isinstance(c, str)
                            and re.fullmatch(r"CWE-\d+", c)), "CWE-1395")
                found.append(_npm_finding(
                    package["name"], _osv_severity(members, group, ids),
                    str(primary.get("summary") or primary.get("id") or ids[0]), cwe,
                    advisory, str(package.get("version", "?")),
                    _osv_fix(members, package["name"], str(package.get("version", "")))
                    if members else NO_FIX[1],
                    lockfile, OSV_SOURCE))
    return found


def _lead(item: object) -> tuple[str, str] | None:
    """(path, one escaped line) for a Semgrep result."""
    if not isinstance(item, dict) or not isinstance(item.get("path"), str) \
            or not isinstance(item.get("check_id"), str):
        raise _Malformed("a Semgrep result must have a check_id and a path")
    start = item.get("start") or {}
    line = start.get("line") if isinstance(start, dict) else None
    if not isinstance(line, int):
        raise _Malformed("a Semgrep result must have a start line")
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    meta = extra.get("metadata") if isinstance(extra.get("metadata"), dict) else {}
    cwe = re.search(r"CWE-\d+", json.dumps(meta.get("cwe", "")))
    path = _lockfile(item["path"])
    text = (f"semgrep {_printable(item['check_id'])} {_printable(path)}:{line} "
            f"{cwe.group() if cwe else 'CWE-?'} {_printable(extra.get('message', ''))}")
    return path, text[:LEAD_MAX]


def _from_semgrep(data: object, scope: dict, out: Path) -> dict[str, int]:
    """One leads file per part: Semgrep results inside the part's files, escaped and capped."""
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise _Malformed("Semgrep output must be an object with a results list")
    owner = {f: str(part.get("id", n)) for n, part in enumerate(scope["parts"], 1)
             for f in part["files"]}
    leads: dict[str, list[str]] = {}
    for item in data["results"]:
        path, text = _lead(item)
        if path in owner and len(leads.setdefault(owner[path], [])) < LEADS_PER_PART:
            leads[owner[path]].append(text)
    for part_id, lines in leads.items():
        _write_private(out / f"{_safe_name(part_id)}.txt", "\n".join(lines) + "\n")
    return {k: len(v) for k, v in leads.items()}


def _safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]", "_", value) or "_"


def _rows(lines: list[str], inside_only: bool) -> list[list[str]]:
    rows, inside = [], not inside_only
    for line in lines:
        if line.strip() == "=== PII INVENTORY ===":
            inside = True
            continue
        if line.strip().startswith("===") and inside_only:
            inside = False
            continue
        cells = [_printable(c.strip()) for c in line.strip().strip("|").split("|")]
        if not inside or len(cells) != len(INVENTORY_COLUMNS) or not cells[0]:
            continue
        if cells[0].lower() == "field" or set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def _inventory(text: str, earlier: str = "") -> str:
    """Merge the auditors' PII inventory blocks, and an earlier inventory, one row per field."""
    merged: dict[str, list[list[str]]] = {}
    rows = _rows(earlier.splitlines(), inside_only=False) + _rows(text.splitlines(), True)
    for cells in rows:
        columns = merged.setdefault(cells[0], [[] for _ in INVENTORY_COLUMNS[1:]])
        for column, cell in zip(columns, cells[1:], strict=True):
            for part in cell.split("; "):
                if part not in ("", "-") and part not in column:
                    column.append(part)
    lines = ["| " + " | ".join(INVENTORY_COLUMNS) + " |",
             "|" + "---|" * len(INVENTORY_COLUMNS)]
    for field in sorted(merged):
        lines.append(f"| {field} | " + " | ".join("; ".join(c) or "-" for c in merged[field])
                     + " |")
    return _scrub("\n".join(lines)) + "\n"


def _where(text: str) -> list[str]:
    return [line.strip() for line in _parse(text)[1].get("Where", []) if line.strip()]


def _spots(line: str) -> list[str]:
    """The `path:line` citations in a Where line."""
    # A backticked citation is read whole, so a folder name with a space stays one path.
    quoted = [m[1] for m in QUOTED_PATH_LINE.finditer(line)]
    return quoted or [m[0] for m in PATH_LINE.finditer(line)]


def _in_repo(name: str, root: Path) -> Path | None:
    """The cited file's resolved path, or None when it lies outside the repo."""
    # Decided from the text before anything touches the disk: resolving `\\host\share\x`
    # makes Windows connect to that host with the owner's credentials.
    if name.startswith(("\\\\", "//")):
        return None
    normal = Path(os.path.normpath(root / name))  # an absolute name replaces root
    if not normal.is_relative_to(root):
        return None
    path = normal.resolve()
    return path if path.is_relative_to(root) else None


def _citation_problems(text: str, repo: Path) -> list[str]:
    """Where lines that don't name a real line of a file in the repo."""
    # Named by position, never by text: a "citation" can be a secret the auditor quoted.
    found = []
    root = repo.resolve()
    for row, line in enumerate(_where(text), 1):
        for number, spot in enumerate(_spots(line), 1):
            at = f"Where line {row}, citation {number}"
            name, line_no = spot.rsplit(":", 1)
            path = _in_repo(name, root)
            if path is None:
                found.append(f"{at}: outside the repo")
            elif not path.is_file():
                found.append(f"{at}: no such file in the repo")
            else:
                count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                if not 1 <= int(line_no) <= count:
                    found.append(f"{at}: past the end of the file ({count} lines)")
    return found


def _key(text: str, repo: Path | None = None) -> tuple[str, str, str]:
    """What makes two findings the same: category, CWE and the root cause's path:line."""
    fields = _parse(text)[0]
    where = _where(text)
    root = next((w for w in where if "fix here" in w.lower()), where[-1] if where else "")
    spots = _spots(root)
    spot = spots[0] if spots else root
    if spots and repo is not None:
        name, number = spot.rsplit(":", 1)
        path = _in_repo(name, repo.resolve())
        if path is not None:
            spot = f"{path.relative_to(repo.resolve()).as_posix()}:{number}"
    return fields.get("Category", ""), fields.get("CWE", ""), spot


def _evidence(text: str) -> str:
    return "\n".join(_parse(text)[1].get("Evidence", []))


def _lockfile(name: str) -> str:
    """One spelling for a lockfile path: `./x`, `.\\x` and `x` are the same file."""
    return PurePosixPath(name.replace("\\", "/")).as_posix()


def _identities(text: str, new: bool = False) -> set[tuple]:
    """What a scripted finding is, wherever it sits; empty for an agent's finding.

    A secret is known by its keyed id, so a rotated key at the same place is a new finding. One
    written before ids existed is known by path, pattern and length until a re-check records its
    id; a new finding (new=True) also answers to that older key, so it can match one.
    """
    fields = _parse(text)[0]
    evidence = _evidence(text)
    if fields.get("Category") == "secrets" and SCAN_MARK.search(evidence):
        found = SECRET_EVIDENCE.search(evidence)
        if found:
            legacy = ("secret-legacy", found["path"], found["pattern"], found["length"])
            ids = set(SECRET_ID.findall(text)) | ({found["id"]} if found["id"] else set())
            keys = {("secret", found["path"], i) for i in ids}
            return keys | {legacy} if new or not keys else keys
    if fields.get("Category") == "dependency" and fields.get("Proof") == "advisory":
        lines = dict(line.split(": ", 1) for line in evidence.splitlines() if ": " in line)
        where = _where(text)
        spots = _spots(where[0]) if where else []
        if spots and "package" in lines and "advisory" in lines:
            lockfile = _lockfile(spots[0].rsplit(":", 1)[0])
            ids = set(ADVISORY_ID.findall(lines["advisory"]))
            return {("dependency", lockfile, lines["package"], i)
                    for i in ids or {lines["advisory"]}}
    return set()


def _secret_line(text: str) -> str | None:
    found = SECRET_EVIDENCE.search(_evidence(text))
    return found["line"] if found else None


def _legacy_pairs(earlier: list[tuple[int, str]], produced: list[str],
                  rotated: set[int]) -> dict[int, str | None]:
    """Which produced secret each pre-id finding is, one to one; None where that isn't clear.

    The pre-id key (path, pattern, length) is shared by every same-shape secret in a file. A
    secret an open finding already holds by id is never paired again. A lone finding takes the
    only secret with its key, or the only one at its line; with siblings on its key (with an
    id or without), it goes by its own line only. A rotated one names the old secret. A
    finding whose key some produced secret shares, held or not, is None when unpaired: it may
    be that secret, so it is never "no longer found".
    """
    held = {k for _, text in earlier for k in _identities(text) if k[0] == "secret"}
    groups: dict[tuple, list[tuple[int, str]]] = {}
    for number, text in earlier:
        key = next((k for k in _identities(text, new=True) if k[0] == "secret-legacy"), None)
        if key:
            groups.setdefault(key, []).append((number, text))
    pairs: dict[int, str | None] = {}
    for key, group in groups.items():
        shared = [t for t in produced if key in _identities(t, new=True)]
        sharing = [t for t in shared if not _identities(t) & held]
        for number, text in group if shared else []:
            if _identities(text) != {key} or number in rotated:
                continue  # it holds an id already, or its old key names the old secret
            same = [t for t in sharing if _secret_line(t) == _secret_line(text)]
            picked = sharing if len(group) == 1 and len(sharing) == 1 else same
            pairs[number] = picked[0] if len(picked) == 1 else None
    taken = [t for t in pairs.values() if t is not None]
    return {n: t if t is None or taken.count(t) == 1 else None for n, t in pairs.items()}


def _rotated(audit: Path) -> set[int]:
    """Numbers accepted.md says were rotated: such a finding's old key names the old secret."""
    try:
        text = (audit.parent / "accepted.md").read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return set()
    return {int(m[1]) for line in text.splitlines()
            if (m := ACCEPT.fullmatch(line.strip())) and m[3]}


def _fix(text: str) -> str:
    """An advisory's fix: the latest a later run reported, else its own."""
    later = FIX_NOW.findall(text)
    return later[-1] if later else next(
        (line[5:].strip() for line in _evidence(text).splitlines() if line.startswith("fix: ")),
        "")


def _committed_secret(text: str) -> bool:
    found = SECRET_EVIDENCE.search(_evidence(text))
    return (bool(found) and found["committed"] == "true") or bool(SEEN_COMMITTED.search(text))


def _severity(text: str) -> str:
    """A finding's severity: its own, or a higher one a later run found it at."""
    rated = [_parse(text)[0].get("Severity", "low"), *SEVERITY_NOW.findall(text)]
    return min(rated, key=lambda s: SEVERITY_RANK.get(s, 3))


def _latest_spot(text: str) -> str | None:
    moved = STATUS.findall(text)
    return moved[-1] if moved else None


def _keys(text: str, repo: Path | None = None, new: bool = False) -> set[tuple]:
    """Every key a finding answers to: its identity, or its root cause and where it moved."""
    ident = _identities(text, new)
    if ident:
        return ident
    category, cwe, spot = _key(text, repo)
    keys = {(category, cwe, spot)}
    for moved in STATUS.findall(text):
        name, number = moved.rsplit(":", 1)
        path = _in_repo(name, repo.resolve()) if repo is not None else None
        if path is not None:
            moved = f"{path.relative_to(repo.resolve()).as_posix()}:{number}"
        keys.add((category, cwe, moved))
    return keys


def _merge_where(path: Path, extra: list[str]) -> None:
    """Add Where lines from a dropped duplicate to the finding that's kept."""
    lines = path.read_text(encoding="utf-8").splitlines()
    have = set(_where("\n".join(lines)))
    new = [line for line in extra if line not in have]
    start = end = None
    # Headings are found the way _parse finds them: outside code blocks, spacing ignored.
    for i, (line, fence) in enumerate(fenced(lines)):
        if fence or not line.startswith("## "):
            continue
        if start is None and line[3:].strip() == "Where":
            start = i
        elif start is not None:
            end = i
            break
    if not new or start is None:
        return
    end = len(lines) if end is None else end
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    _write_private(path, "\n".join(lines[:end] + new + lines[end:]) + "\n")


def _dedupe(new: Path, audit: Path, repo: Path | None = None) -> list[str]:
    """Drop new findings already in the audit folder, or repeated, keeping the most severe."""
    if new.resolve() == audit.resolve():
        raise _Malformed("dedupe needs two folders; given the same folder twice")
    seen_before: dict[tuple, Path] = {}
    earlier_texts = []
    for number, earlier in _open(audit):
        text = earlier.read_text(encoding="utf-8", errors="replace")
        earlier_texts.append((number, text, earlier))
        for key in _keys(text, repo):
            if key[0] != "secret-legacy":
                seen_before.setdefault(key, earlier)
    today = datetime.date.today().isoformat()
    candidates = []
    for path in sorted(new.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        severity = _parse(text)[0].get("Severity", "low")
        candidates.append((SEVERITY_RANK.get(severity, 3), path.name, path,
                           _keys(text, repo, new=True), _keys(text, repo), text))
    pairs = _legacy_pairs([(n, t) for n, t, _ in earlier_texts], [c[5] for c in candidates],
                          _rotated(audit))
    kept: dict[tuple, Path] = {}
    removed = []
    for _, _, path, matching, own, text in sorted(candidates, key=lambda c: c[:2]):
        if hits := [seen_before[k] for k in matching if k in seen_before] + [
                p for n, _, p in earlier_texts if n in pairs and pairs[n] == text]:
            # Found again at a higher severity (a secret since committed, a revised advisory):
            # the earlier number now carries it, below its untouched evidence.
            severity = _parse(text)[0].get("Severity")
            for earlier in dict.fromkeys(hits):
                earlier_text = earlier.read_text(encoding="utf-8", errors="replace")
                current = _severity(earlier_text)
                if severity in SEVERITIES and SEVERITIES.index(severity) < SEVERITIES.index(
                        current if current in SEVERITIES else "low"):
                    _append(earlier, f"**Status ({today}):** severity now {severity} "
                                     "(found again at it)")
                # A fix released since: the report stops saying no fix is known.
                fix = _one_line(_fix(text))
                if _identities(text) and _fix(text) and fix != _fix(earlier_text):
                    _append(earlier, f"**Status ({today}):** fix now {fix}")
            path.unlink()
            removed.append(path.name)
        # Within one run only a finding's own keys merge: two keys at one place aren't one.
        elif same := next((kept[k] for k in own if k in kept), None):
            _merge_where(same, _where(path.read_text(encoding="utf-8", errors="replace")))
            path.unlink()
            removed.append(path.name)
        else:
            kept.update(dict.fromkeys(own, path))
    return removed


def _open(audit: Path) -> list[tuple[int, Path]]:
    """The numbered findings not fixed: one also in fixed/ was moved by a run that stopped."""
    fixed = {n for n, _ in numbered(audit / "fixed")}
    return [(n, p) for n, p in numbered(audit) if n not in fixed]


def _strings(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _Malformed(f"{name} must be a list of strings")
    return value


def _records(value: object, name: str, keys: dict[str, type]) -> list[dict]:
    if not isinstance(value, list) or not all(
        isinstance(v, dict) and all(isinstance(v.get(k), t) for k, t in keys.items())
        for v in value
    ):
        raise _Malformed(f"{name} must be a list of {{{', '.join(keys)}}} objects")
    return value


def _check_meta(meta: object) -> dict:
    """The run's own facts: what ran, what failed, and the agent findings check refused."""
    if not isinstance(meta, dict):
        raise _Malformed("--meta must be a JSON object")
    _strings(meta.get("audited", []), "--meta audited")
    _records(meta.get("audit_failures", []), "--meta audit_failures",
             {"lockfile": str, "reason": str})
    for item in _records(meta.get("check_failed", []), "--meta check_failed",
                         {"file": str, "problems": list}):
        _strings(item["problems"], "--meta check_failed problems")
    _strings(meta.get("history_unknown", []), "--meta history_unknown")
    if not isinstance(meta.get("leads_run", True), bool):
        raise _Malformed("--meta leads_run must be true or false")
    return meta


def _check_scope(scope: object) -> dict:
    """scope.py's JSON: the parts, those --max left out, the audits and the coverage facts."""
    if not isinstance(scope, dict):
        raise _Malformed("--scope must be scope.py's JSON object")
    for key in ("parts", "skipped", "audits"):
        if key not in scope:
            raise _Malformed(f"--scope has no {key}: give it scope.py's --focus security JSON")
    for key in ("parts", "skipped"):
        for part in _records(scope[key], f"--scope {key}", {"dir": str, "files": list}):
            _strings(part["files"], f"--scope {key} files")
            for field in ("checklists", "no_checklist"):
                if field in part:
                    _strings(part[field], f"--scope {key} {field}")
    _records(scope["audits"], "--scope audits", {"lockfile": str})
    cover = scope.get("coverage", {})
    if not isinstance(cover, dict):
        raise _Malformed("--scope coverage must be an object")
    # A missing fact is a gap in the report; a fact of the wrong type is an error.
    for key in ("paths", "unsafe_folders", "manifests_without_lockfile", "unaudited_lockfiles",
                "submodules"):
        if key in cover:
            _strings(cover[key], f"--scope coverage {key}")
    other = cover.get("other_files", {})
    if not isinstance(other, dict) or not all(
            isinstance(k, str) and type(v) is int for k, v in other.items()):
        raise _Malformed("--scope coverage other_files must map extensions to counts")
    if not (cover.get("dirty") is None or type(cover.get("dirty")) is bool):
        raise _Malformed("--scope coverage dirty must be true, false or null")
    if not isinstance(cover.get("commit"), (str, type(None))):
        raise _Malformed("--scope coverage commit must be text or null")
    return scope


def _check_recheck(data: object) -> dict:
    if not isinstance(data, dict):
        raise _Malformed("--recheck must be recheck's JSON object")
    _records(data.get("cannot_check", []), "--recheck cannot_check",
             {"number": str, "reason": str})
    _strings(data.get("not_rechecked", []), "--recheck not_rechecked")
    _strings(data.get("unpaired", []), "--recheck unpaired")
    return data


def _piece(value: object) -> str:
    """Untrusted text set into a report line: control characters escaped, a secret withheld."""
    raw = str(value)
    text = _printable(raw)
    # Withheld on its own, so the rest of the line (a finding's number) still shows.
    return "(withheld)" if _secret_hits(raw) or _secret_hits(text) else text


def _gaps(scope: dict | None, meta: dict | None, recheck: dict | None,
          unreadable: list[str], rejected: list[dict]) -> list[str]:
    """Everything that keeps the verdict from Safe to deploy, short of a blocking finding."""
    p = _piece
    gaps = []
    if scope is None:
        gaps.append("coverage not reported: the report was written without --scope")
    else:
        for part in scope["skipped"]:
            gaps.append(f"part not audited (--max): {p(part['dir'])} "
                        f"({len(part['files'])} files)")
        cover = scope.get("coverage", {})
        for key in ("paths", "commit", "dirty", "unsafe_folders", "other_files",
                    "manifests_without_lockfile", "unaudited_lockfiles"):
            if key not in cover:
                gaps.append(f"coverage fact not reported: {key}")
        if cover.get("paths"):
            gaps.append("only part of the repo was in scope: "
                        + ", ".join(map(p, cover["paths"])))
        gaps += [f"folder skipped for an unsafe name: {p(f)}"
                 for f in cover.get("unsafe_folders", [])]
        missing: dict[str, list[str]] = {}
        for part in scope["parts"]:
            if "no_checklist" not in part:
                gaps.append(f"coverage fact not reported: checklists for {p(part['dir'])}")
            for name in part.get("no_checklist", []):
                missing.setdefault(name, []).append(part["dir"])
        gaps += [f"no checklist of its own for {p(name)}: {', '.join(map(p, dirs))}"
                 for name, dirs in missing.items()]
        gaps += [f"{n} files in {p(ext)} with no checklist"
                 for ext, n in cover.get("other_files", {}).items()]
        gaps += [f"manifest with no lockfile: {p(m)}"
                 for m in cover.get("manifests_without_lockfile", [])]
        gaps += [f"lockfile with no dependency audit: {p(f)}"
                 for f in cover.get("unaudited_lockfiles", [])]
        gaps += [f"submodule not checked for uncommitted changes: {p(s)}"
                 for s in cover.get("submodules", [])]
        if "commit" in cover and not cover["commit"]:
            gaps.append("couldn't tell which commit was audited")
        if cover.get("dirty") is True:
            gaps.append("uncommitted changes: this result matches no commit")
        elif "dirty" in cover and cover["dirty"] is None:
            gaps.append("couldn't tell whether there are uncommitted changes")
        if meta is not None:
            audited = {_lockfile(a) for a in meta.get("audited", [])}
            reasons = {_lockfile(f["lockfile"]): f["reason"]
                       for f in meta.get("audit_failures", [])}
            for audit in scope["audits"]:
                name = _lockfile(audit["lockfile"])
                if name not in audited:
                    reason = reasons.get(name)
                    gaps.append(f"dependency audit didn't run or failed: {p(name)}"
                                + (f" ({p(reason)})" if reason else ""))
    if meta is None:
        gaps.append("run facts not reported (no --meta): whether the secrets scan and the "
                    "dependency audits ran is unknown")
    else:
        if meta.get("secrets_scanned") is not True:
            gaps.append("secrets scan didn't run")
        gaps += [f"{p(f['file'])} failed the format check, so no verifier saw it: "
                 + "; ".join(map(p, f["problems"])) for f in meta.get("check_failed", [])]
        gaps += [f"couldn't tell whether git history holds {p(name)}, so its secret may be "
                 "committed" for name in meta.get("history_unknown", [])]
    if recheck is None:
        gaps.append("earlier findings' re-check not reported (no --recheck)")
    else:
        gaps += [f"earlier finding {p(c['number'])} couldn't be re-checked: {p(c['reason'])}"
                 for c in recheck.get("cannot_check", [])]
        outside = recheck.get("not_rechecked", [])
        if outside:
            gaps.append(f"{len(outside)} earlier findings not re-checked: outside this run's "
                        f"scope ({', '.join(map(p, outside))})")
    gaps += [f"{name} fails the format check, so it's skipped and not counted"
             for name in unreadable]
    gaps += [f"{p(r['file'])} has no usable verifier verdict, so it was neither confirmed "
             "nor ruled out" for r in rejected if r.get("no_verdict")]
    return gaps


def _accepted(path: Path, open_findings: dict[int, dict], today: datetime.date
              ) -> tuple[dict[int, str], dict[int, str], list[str]]:
    """The owner's accepted.md: what it accepts, what has expired, and lines that accept nothing."""
    accepted: dict[int, str] = {}
    expired: dict[int, str] = {}
    invalid: list[str] = []
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        return accepted, expired, invalid
    except UnicodeDecodeError:
        return accepted, expired, ["accepted.md isn't UTF-8, so nothing in it is accepted"]
    except OSError as exc:
        return accepted, expired, [f"accepted.md can't be read ({exc.strerror})"]
    # Lines are named by position; a reason is the owner's text and goes out through _piece.
    for row, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or not (line[0] in "-*+" or line[0].isdigit()):
            continue
        found = ACCEPT.fullmatch(line)
        if not found:
            invalid.append(f"line {row}: not `- NN until YYYY-MM-DD: reason` "
                           "or `- NN rotated: note`")
            continue
        number, until, rotated, reason = int(found[1]), found[2], found[3], _piece(found[4])
        fields = open_findings.get(number)
        if fields is None:
            invalid.append(f"line {row}: no open finding {number:02d}")
        elif rotated:
            if fields.get("Category") != "secrets":
                invalid.append(f"line {row}: `rotated` is only for secrets findings")
            else:
                accepted[number] = f"rotated: {reason}"
        else:
            try:
                day = datetime.date.fromisoformat(until)
            except ValueError:
                invalid.append(f"line {row}: {until} isn't a real date")
                continue
            target = expired if day < today else accepted
            target[number] = f"until {until}: {reason}"
    return accepted, expired, invalid


def _owasp(fields: dict) -> str:
    found = re.fullmatch(r"CWE-([0-9]{1,6})", fields.get("CWE", ""))
    return OWASP_OF.get(int(found[1]), "unmapped") if found else "unmapped"


def _checked_categories(scope: dict | None) -> set[str]:
    """OWASP categories that at least one of this run's checklists has an item for."""
    names = {n for part in (scope or {}).get("parts", []) for n in part.get("checklists", [])}
    checked = set()
    for name in names:
        path = CHECKLIST_DIR / f"{name}.md"
        if re.fullmatch(r"[a-z0-9-]+", name) and path.is_file():
            for cwe in re.findall(r"CWE-([0-9]{1,6})", path.read_text(encoding="utf-8")):
                if int(cwe) in OWASP_OF:
                    checked.add(OWASP_OF[int(cwe)])
    return checked


def _rejected(folder: Path) -> tuple[list[dict], bool]:
    """The suspects `suspects` refused, and whether that record could be read."""
    path = folder / REJECTED
    if not path.exists():
        return [], True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _records(data, "rejected", {"file": str, "problems": list}), True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, _Malformed):
        return [], False


def _suspects(folder: Path, rejected: list[dict]) -> list[str]:
    """Worth a look: each unconfirmed suspect as one line, then those refused by file name."""
    lines = []
    for path in sorted((folder / "unconfirmed").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fields = _parse(text)[0]
        where = next((s for line in _where(text) for s in _spots(line)), "?")
        verdict = next((line[len("Verifier: "):] for line in reversed(text.splitlines())
                        if line.startswith("Verifier: ")), "?")
        lines.append(f"- {_piece(title(path) or path.name)} (`{_piece(where)}`, "
                     f"{_piece(fields.get('Severity', '?'))} as written): {_piece(verdict)}")
    lines += [f"- {_piece(r['file'])}: " + "; ".join(map(_piece, r["problems"]))
              for r in rejected]
    return lines


def _report(folder: Path, meta: dict | None, scope: dict | None = None,
            recheck: dict | None = None, sealed: bool = True) -> str:
    today = datetime.date.today()
    good, skipped, written = [], [], {}
    for number, path in _open(folder):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _problems(text):
            skipped.append(path.name)
            continue
        fields, sections = _parse(text)
        written[number] = fields["Severity"]
        fields = {**fields, "Severity": _severity(text)}
        where = _latest_spot(text) or next((PATH_LINE.search(line)[0]
                                            for line in sections["Where"]
                                            if PATH_LINE.search(line)), "")
        no_fix = bool(_identities(text)) and _fix(text) in NO_FIX
        head = title(path)
        local = SECRET_EVIDENCE.search(_evidence(text))
        if (fields["Category"] == "secrets" and local and local["committed"] == "false"
                and _committed_secret(text)):
            head += " (since committed)"
        good.append((SEVERITIES.index(fields["Severity"]), number, fields, head, where,
                     no_fix))
    good.sort(key=lambda g: (g[0], g[1]))
    accepted, expired, invalid = _accepted(folder.parent / "accepted.md",
                                           {g[1]: g[2] for g in good}, today)
    blocking = []
    for rank, number, fields, head, _, no_fix in good:
        if rank > SEVERITIES.index("high") or number in accepted:
            continue
        note = (f" — acceptance expired ({expired[number]})" if number in expired else
                " — no fix known: replace the package or accept it with a date" if no_fix
                else "")
        blocking.append(f"- {number:02d} ({fields['Severity']}): {_piece(head)}{note}")
    rejected, readable = _rejected(folder)
    gaps = _gaps(scope, meta, recheck, skipped, rejected)
    if not readable:
        gaps.append("the list of refused suspects can't be read")
    outcome = "Blocked" if blocking else "Not verified" if gaps else "Safe to deploy"
    cover = (scope or {}).get("coverage", {})
    dirty = {False: "no uncommitted changes", True: "uncommitted changes included"}.get(
        cover.get("dirty"), "unknown whether uncommitted changes were included")

    out = ["# Security and PII audit", "", f"## Verdict: {outcome}",
           f"Covers commit {_piece(cover.get('commit') or 'unknown')} ({dirty}), audited "
           f"{today.isoformat()}, code only, no live environment.", ""]
    if blocking:
        out += ["Blocking (open, critical or high, not accepted):", *blocking, ""]
    if gaps:
        out += ["Coverage gaps (each keeps this from reading Safe to deploy):",
                *[f"- {g}" for g in gaps], ""]
    # Without the seal, an edit made during the run (an acceptance, the policy, a finding)
    # isn't ruled out; the verdict's facts are the same, so a note rather than a gap.
    if meta is not None and not sealed:
        out += ["Note: this report ran without --seal, so an edit to accepted.md, policy.md or "
                "a finding during the run isn't ruled out.", ""]
    if recheck is not None and recheck.get("sealed") is False:
        out += ["Note: the re-check ran without --seal, so an edit made before it moved "
                "findings isn't ruled out.", ""]
    if recheck is not None:
        out += [f"Note: earlier finding {_piece(nn)} stays open: a secret of the same shape is "
                "still in its file, and which one it was can't be told. Once its key is "
                f"rotated, close it with `- {_piece(nn)} rotated: <note>` in accepted.md."
                for nn in recheck.get("unpaired", [])]
        if recheck.get("unpaired"):
            out.append("")
    if meta is not None and meta.get("leads_run") is not True:
        out += ["Note: Semgrep leads not run (not installed or it failed); the auditors read "
                "every part from its checklists alone. This doesn't change the verdict.", ""]
    if accepted:
        severity = {g[1]: g[2]["Severity"] for g in good}

        def rated(n: int) -> str:
            if severity[n] == written[n]:
                return severity[n]
            return f"{severity[n]}, raised from {written[n]} since it was first found"

        out += ["Accepted (doesn't block until its date; rotated secrets for good):",
                *[f"- {n:02d} ({rated(n)}) {entry}" for n, entry in sorted(accepted.items())],
                ""]
    if expired:
        out += ["Expired acceptances (they no longer accept anything):",
                *[f"- {n:02d} {entry}" for n, entry in sorted(expired.items())], ""]
    if invalid:
        out += ["Invalid lines in accepted.md (they accept nothing):",
                *[f"- {line}" for line in invalid], ""]
    if meta and meta.get("policy"):
        out.append("Access policy: the owner's policy file was used.")
    else:
        out.append("No policy file was used: authorization findings that rest on an assumed "
                   "policy say so and are capped at medium.")
    out += ["", "## Findings", "",
            "| # | severity | category | OWASP | proof | title | where |",
            "|---|---|---|---|---|---|---|"]
    for _, number, fields, head, where, _ in good:
        out.append(f"| {number:02d} | {fields['Severity']} | {fields['Category']} | "
                   f"{_owasp(fields)} | {fields['Proof']} | {_piece(head)} | "
                   f"`{_piece(where)}` |")
    out += ["", "## Counts", ""]
    for severity in SEVERITIES:
        out.append(f"- {severity}: {sum(1 for g in good if g[2]['Severity'] == severity)}")
    for category in CATEGORIES:
        count = sum(1 for g in good if g[2]["Category"] == category)
        if count:
            out.append(f"- {category}: {count}")
    checked = _checked_categories(scope)
    out += ["", "## OWASP Top 10 (2025)", "",
            "| category | title | this run's checklists | critical | high | medium | low |",
            "|---|---|---|---|---|---|---|"]
    for cat, name in OWASP_TITLES.items():
        counts_ = [sum(1 for g in good if _owasp(g[2]) == cat and g[2]["Severity"] == sev)
                   for sev in SEVERITIES]
        state = "checked" if cat in checked else "not checked"
        out.append(f"| {cat} | {name} | {state} | " + " | ".join(map(str, counts_)) + " |")
    inventory_file = folder / "inventory.md"
    if inventory_file.is_file():
        # Cells are agent text; an inventory written before cells were escaped may hold ESC.
        out += ["", "## PII inventory", "",
                *map(_printable, inventory_file.read_text(encoding="utf-8").rstrip().split("\n"))]
    out += ["", "## Worth a look (unconfirmed, doesn't block)", "",
            *_suspects(folder, rejected)]
    out += [f"- {_piece(f['file'])}: " + "; ".join(map(_piece, f["problems"]))
            for f in (meta or {}).get("check_failed", [])]
    fixed = numbered(folder / "fixed")
    if fixed:
        out += ["", "## Fixed", "",
                f"{len(fixed)} earlier findings are fixed; each is in fixed/ with its date and "
                "reason."]
    return _scrub("\n".join(out)) + "\n"


def _one_line(text: str) -> str:
    """Agent text kept after the run: one line, and withheld if it holds a known secret."""
    return _piece(" ".join(text.split()))


def _last_line(text: str) -> str:
    return next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")


def _root_file(text: str, repo: Path | None) -> str:
    """The root cause's file: where a re-check last found it, else the finding's own."""
    return (_latest_spot(text) or _key(text, repo)[2]).rsplit(":", 1)[0]


def _left_out(name: str, scope: dict) -> bool:
    """Whether this run's own limits (paths…, --max) kept a file out of the audit."""
    paths = scope.get("coverage", {}).get("paths") or []
    skipped = {f for part in scope["skipped"] for f in part["files"]}
    under = not paths or any(p in ("", ".") or name == p or name.startswith(p.rstrip("/") + "/")
                             for p in paths)
    return not under or name in skipped


def _earlier(audit: Path, scope: dict, repo: Path | None) -> tuple[list[str], list[str]]:
    """Open agent findings to re-check, and those this run's limits leave out."""
    inside, outside = [], []
    for number, path in _open(audit):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not _identities(text):
            (outside if _left_out(_root_file(text, repo), scope) else inside).append(
                f"{number:02d}")
    return inside, outside


def _append(path: Path, line: str, to: Path | None = None) -> None:
    """Add one line below a finding, byte for byte as it was: evidence is never rewritten."""
    data = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    _write_private(to or path, data.rstrip(b"\r\n") + newline * 2 + line.encode() + newline)


def _move_fixed(path: Path, reason: str, today: str) -> None:
    # Written before the original goes: a crash between leaves both, which counts as fixed.
    _append(path, f"**Fixed ({today}):** {_one_line(reason)}", path.parent / "fixed" / path.name)
    path.parent.joinpath("fixed").chmod(0o700)
    path.unlink()


def _hash_files(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        name = os.fsencode(path.relative_to(root))
        # Length-framed, so no two sets of files hash alike; a missing file counts too.
        data = path.read_bytes() if path.exists() else None
        digest.update(len(name).to_bytes(8, "big") + name)
        digest.update(b"\0" if data is None else b"\1" + len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def _seal(audit: Path) -> str:
    """`<owner's files>.<findings>`: hashes of what agents must not change during a run."""
    # Two parts: recheck and dedupe change findings on purpose, never the owner's files.
    owners = _hash_files(audit.parent, [audit.parent / "accepted.md", audit.parent / "policy.md"])
    findings = _hash_files(audit.parent, [
        *sorted(p for p in audit.glob("*.md") if p.name != "REPORT.md"),
        *sorted((audit / "fixed").glob("*.md"))])
    return f"{owners}.{findings}"


def _check_seal(audit: Path, seal: str | None, whole: bool) -> None:
    if seal is None:
        return
    now = _seal(audit)
    if (now if whole else now.split(".")[0]) != (seal if whole else seal.split(".")[0]):
        raise _Malformed("accepted.md, policy.md or the audit folder changed since the run "
                         "began, so nothing was written: look at what changed, then run "
                         "/audit again")


def _verdict_spot(spot: str, repo: Path | None) -> str | None:
    """A re-check's new location as repo-relative `path:line`, or None if it isn't a real line."""
    if not spot.isprintable() or _secret_hits(spot):
        return None
    if repo is None:
        return spot
    name, number = spot.rsplit(":", 1)
    root = repo.resolve()
    try:
        path = _in_repo(name, root)
        if path is None or not path.is_file():
            return None
        count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        line = int(number)
    except (OSError, ValueError):
        return None  # an unreadable file or a number too long to read: not a real line
    return f"{path.relative_to(root).as_posix()}:{line}" if 1 <= line <= count else None


def _recheck(audit: Path, scope: dict, found: Path | None, verdicts: dict[str, str],
             secrets_scanned: bool, audited: list[str], repo: Path | None) -> dict:
    today = datetime.date.today().isoformat()
    fixed_folder = audit / "fixed"
    for _, path in numbered(audit):
        if (fixed_folder / path.name).exists():
            path.unlink()  # finishes a move a stopped run left half done
    produced: dict[tuple, list[str]] = {}
    produced_texts = []
    for p in sorted(found.glob("*.md")) if found is not None else []:
        text = p.read_text(encoding="utf-8", errors="replace")
        produced_texts.append(text)
        for key in _identities(text, new=True):
            produced.setdefault(key, []).append(text)
    audited_set = {_lockfile(a) for a in audited}
    rotated = _rotated(audit)
    pairs = _legacy_pairs([(n, p.read_text(encoding="utf-8", errors="replace"))
                           for n, p in numbered(audit)], produced_texts, rotated)
    result: dict[str, list] = {"fixed": [], "still_open": [], "cannot_check": [],
                               "not_rechecked": [], "unpaired": []}
    for number, path in numbered(audit):
        nn = f"{number:02d}"
        text = path.read_text(encoding="utf-8", errors="replace")
        idents = _identities(text)
        if idents:
            kind = next(iter(idents))[0]
            if kind == "dependency":
                lockfile = next(iter(idents))[1]
                if lockfile not in audited_set:
                    held = repo is not None and _in_repo(lockfile, repo.resolve())
                    if _left_out(lockfile, scope):
                        result["not_rechecked"].append(nn)
                    # Gone only from a clean tree: a delete not yet committed still ships.
                    elif (repo is not None and held is not None and not held.exists()
                          and scope.get("coverage", {}).get("dirty") is False):
                        reason = f"its lockfile {_piece(lockfile)} is gone from the repo"
                        _move_fixed(path, reason, today)
                        result["fixed"].append({"number": nn, "reason": reason})
                    else:
                        result["cannot_check"].append({"number": nn, "reason": (
                            f"its lockfile {_piece(lockfile)} wasn't audited this run")})
                    continue
            elif not secrets_scanned:
                continue  # the report already names the scan that didn't run
            matches = [t for key in idents for t in produced.get(key, [])]
            if kind == "secret-legacy":
                if number in pairs and pairs[number] is None:
                    # Same-shape secrets are there, but which one this is isn't clear.
                    result["still_open"].append(nn)
                    result["unpaired"].append(nn)
                    continue
                matches = [pairs[number]] if number in pairs else []
            if matches:
                if kind != "dependency":
                    new_ids = {i for t in matches for i in SECRET_ID_IN_EVIDENCE.findall(t)}
                    for new_id in sorted(new_ids - {k[2] for k in idents if k[0] == "secret"}):
                        _append(path, f"**Status ({today}):** secret id {new_id}")
                    if not _committed_secret(text) and any(map(_committed_secret, matches)):
                        _append(path, f"**Status ({today}):** seen committed")
                result["still_open"].append(nn)
                continue
            if kind != "dependency":
                secret_path = SECRET_EVIDENCE.search(_evidence(text))["path"]
                # Deleting a committed secret leaves it in history: it stays until rotated.
                # Without the repo, or when git can't say, nothing is fixed blind.
                if (_committed_secret(text) or repo is None
                        or in_history(str(repo), secret_path) is not False):
                    result["still_open"].append(nn)
                    continue
            reason = ("no longer found by the secrets scan" if kind != "dependency" else
                      f"no longer reported by the dependency audit of {lockfile}")
            if kind == "dependency" and not any(ADVISORY_ID.search(k[3]) for k in idents):
                package = next(iter(idents))[2]
                if any(k[0] == "dependency" and k[1] == lockfile and k[2] == package
                       for k in produced):
                    # No id to match it by, and its package is still reported: it may well
                    # be the same advisory, so it stays open with its number and acceptance.
                    result["still_open"].append(nn)
                    continue
                if any(k[3] == NPM_THROUGH for k in idents) and any(
                        OSV_SOURCE in t and k[1] == lockfile
                        for t in produced_texts for k in _identities(t)):
                    # npm lists a package that only brings a vulnerable one in; OSV-Scanner
                    # reports the vulnerable package itself, as its own finding.
                    reason = ("superseded: OSV-Scanner reports the vulnerable package itself, "
                              "not the one that brings it in")
            if kind == "secret-legacy" and number in rotated:
                reason = "rotated (accepted.md)" + (
                    "; the key now at this path is a separate finding"
                    if any(produced.get(key) for key in idents) else f" and {reason}")
            _move_fixed(path, reason, today)
            result["fixed"].append({"number": nn, "reason": _one_line(reason)})
            continue
        if _left_out(_root_file(text, repo), scope):
            result["not_rechecked"].append(nn)
            continue
        reply = verdicts.get(nn, "")
        line = _last_line(reply)
        still, fixed = STILL_OPEN.fullmatch(line), FIXED.fullmatch(line)
        cannot = CANNOT_CHECK.fullmatch(line)
        if still:
            spot = _verdict_spot(still[1] or still[2], repo)
            if spot is None:
                result["cannot_check"].append({
                    "number": nn, "reason": "the verifier's new location isn't a real line in "
                                            "the repo"})
                continue
            if spot != (_latest_spot(text) or _key(text, repo)[2]):
                _append(path, f"**Status ({today}):** still open at `{spot}`")
            result["still_open"].append(nn)
        elif fixed:
            _move_fixed(path, fixed[1], today)
            result["fixed"].append({"number": nn, "reason": _one_line(fixed[1])})
        else:
            why = ("no re-check verdict" if not line else
                   _one_line(cannot[1]) if cannot and cannot[1] else
                   "the verifier said CANNOT CHECK" if cannot else
                   "the verifier's verdict line couldn't be read")
            result["cannot_check"].append({"number": nn, "reason": why})
    return result


def _leads(folder: Path | None) -> tuple[set[str], set[str]]:
    """This run's lead rule ids and their `path:line` spots."""
    rules, spots = set(), set()
    for path in sorted(folder.glob("*.txt")) if folder is not None else []:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if found := LEAD_LINE.match(line):
                rules.add(found[1].casefold())
                spots.add(f"{_lockfile(found[2])}:{found[3]}")
    return rules, spots


def _plain(text: str) -> str:
    """Text folded so a look-alike or hidden character can't hide a word: NFKC, no format chars."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(c for c in folded if unicodedata.category(c) != "Cf")


def _agent_problems(text: str, leads: tuple[set[str], set[str]] = (set(), set())) -> list[str]:
    """Marks only the scripts write: an agent's finding carrying one is posing as their output."""
    # Line breaks as _parse sees them: a form feed or U+2028 also starts a line there.
    lines = "\n".join(text.splitlines())
    found = [problem for pattern, problem in SCRIPT_ONLY if pattern.search(lines)]
    fields, sections = _parse(text)
    spots = {f"{_lockfile(s.rsplit(':', 1)[0])}:{s.rsplit(':', 1)[1]}"
             for line in sections.get("Where", []) for s in _spots(line)}
    plain = _plain(lines)
    rules, lead_spots = leads
    # A rule id only as a whole token: the words it is named after aren't a citation.
    cited = any(re.search(rf"(?<![\w.-]){re.escape(r)}(?![\w-]|\.\w)", plain) for r in rules)
    if SEMGREP.search(plain) or cited or spots & lead_spots:
        if fields.get("Proof") not in ("traced", "proven") or len(spots) < 2:
            found.append("cites a Semgrep lead: a lead is only a pointer; it needs Proof "
                         "traced or proven and a source-to-sink trace (two path:line spots "
                         "in ## Where)")
    return found


def _keep_suspects(src: Path, audit: Path, leads: Path | None = None) -> list[str]:
    """Replace audit/unconfirmed with this run's suspects that pass check; the problems found."""
    folder = audit / "unconfirmed"
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    for old in folder.glob("*.md"):
        old.unlink()
    rejected, lead_marks = [], _leads(leads)
    for path in sorted(src.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        verdict_file = path.with_suffix(".verdict")
        verdict = (_last_line(verdict_file.read_text(encoding="utf-8", errors="replace"))
                   if verdict_file.is_file() else "")
        found = _problems(text) + _agent_problems(text, lead_marks)
        no_verdict = not UNCONFIRMED.fullmatch(verdict)
        if not verdict:
            found.append("no verifier verdict")
        elif no_verdict:
            found.append("its verdict isn't NOT CONFIRMED or CANNOT CHECK")
        elif _secret_hits(verdict):
            found.append("its verdict line looks like it holds a secret")
        if found:
            # By file name and problems only: the text may hold a secret.
            rejected.append({"file": path.name, "problems": found, "no_verdict": no_verdict})
            continue
        _write_private(folder / path.name, text.rstrip("\n") + f"\n\nVerifier: {verdict}\n")
    _write_private(audit / REJECTED, json.dumps(rejected, indent=2) + "\n")
    return [f"skipped {_piece(r['file'])}: " + "; ".join(r["problems"]) for r in rejected]


def _error_text(value: object) -> str:
    """One capped line: an error can quote the target's own names."""
    return _printable(value)[:ERROR_MAX]


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").add_argument("file")
    sub.add_parser("dir").add_argument("repo")
    sub.add_parser("next").add_argument("dir")
    sub.choices["check"].add_argument("--fingerprints")
    sub.choices["check"].add_argument("--repo")
    sub.choices["check"].add_argument("--agent", action="store_true",
                                      help="an agent wrote it: refuse marks only scripts write")
    sub.choices["check"].add_argument("--leads", help="this run's leads folder (from-semgrep)")
    for name in ("from-secrets-scan", "from-npm-audit", "from-composer-audit",
                 "from-osv-scanner"):
        p = sub.add_parser(name)
        p.add_argument("json")
        p.add_argument("out")
        p.add_argument("--lockfile")
    sub.choices["from-osv-scanner"].add_argument(
        "--exit", type=int, required=True,
        help="OSV-Scanner's exit code: only 0 (clean) and 1 (advisories) mean it scanned")
    p = sub.add_parser("from-semgrep", help="one leads file per part from Semgrep's JSON")
    p.add_argument("json")
    p.add_argument("out")
    p.add_argument("--scope", required=True)
    p = sub.add_parser("inventory")
    p.add_argument("blocks")
    p.add_argument("dir")
    p.add_argument("--fingerprints")
    p = sub.add_parser("dedupe")
    p.add_argument("new")
    p.add_argument("audit")
    p.add_argument("--repo")
    p.add_argument("--seal", help="what `seal` printed: refuse if accepted.md or policy.md "
                                  "changed since")
    p = sub.add_parser("report")
    p.add_argument("dir")
    p.add_argument("--seal", help="what `seal` printed: refuse if accepted.md or policy.md "
                                  "changed since")
    p.add_argument("--meta")
    p.add_argument("--scope", help="scope.py's JSON for this run")
    p.add_argument("--recheck", help="recheck's JSON for this run")
    p.add_argument("--fingerprints")
    p = sub.add_parser("earlier", help="list open agent findings to re-check, and those outside")
    p.add_argument("dir")
    p.add_argument("--scope", required=True)
    p.add_argument("--repo")
    p = sub.add_parser("recheck", help="apply re-check verdicts and re-derive scripted findings")
    p.add_argument("dir")
    p.add_argument("--scope", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--found", help="this run's converted script findings")
    p.add_argument("--verdicts", help="JSON of finding number to the verifier's reply")
    p.add_argument("--secrets-scanned", action="store_true")
    p.add_argument("--audited", action="append", default=[], help="a lockfile audited this run")
    p.add_argument("--repo")
    p.add_argument("--fingerprints")
    p.add_argument("--seal", help="what `seal` printed before any agent ran")
    sub.add_parser("seal", help="hash accepted.md, policy.md and the findings, before agents "
                                "run").add_argument("dir")
    p = sub.add_parser("suspects", help="replace dir/unconfirmed with this run's suspects")
    p.add_argument("src")
    p.add_argument("dir")
    p.add_argument("--fingerprints")
    p.add_argument("--leads", help="this run's leads folder (from-semgrep)")
    args = parser.parse_args(argv)

    try:
        if getattr(args, "fingerprints", None):
            try:
                PRINTS.update(load_prints(_load(args.fingerprints)))
            except ValueError as exc:
                raise _Malformed(f"--fingerprints: {exc}") from exc
        if args.command == "check":
            text = Path(args.file).read_text(encoding="utf-8")
            found = _problems(text)
            if args.repo:
                found += _citation_problems(text, Path(args.repo))
            if args.agent:
                found += _agent_problems(text, _leads(Path(args.leads) if args.leads else None))
            for problem in found:
                print(problem)
            return 1 if found else 0
        if args.command == "dir":
            folder = drafts_dir(args.repo).parent / "audit"
            folder.mkdir(parents=True, exist_ok=True)
            folder.chmod(0o700)
            print(folder)
            return 0
        if args.command == "next":
            # Fixed findings keep their numbers too: a number is never given out twice.
            taken = [n for n, _ in numbered(Path(args.dir)) + numbered(Path(args.dir) / "fixed")]
            print(f"{max(taken, default=0) + 1:02d}")
            return 0
        if args.command == "earlier":
            repo = Path(args.repo) if args.repo else None
            inside, outside = _earlier(Path(args.dir), _check_scope(_load(args.scope)), repo)
            print(json.dumps({"recheck": inside, "outside": outside}))
            return 0
        if args.command == "seal":
            print(_seal(Path(args.dir)))
            return 0
        if args.command == "recheck":
            # Checked before anything moves, so a tampered folder is left as it was found.
            _check_seal(Path(args.dir), args.seal, whole=True)
            verdicts = _load(args.verdicts) if args.verdicts else {}
            if not isinstance(verdicts, dict) or not all(
                    isinstance(v, str) for v in verdicts.values()):
                raise _Malformed("--verdicts must map finding numbers to the verifier's reply")
            result = _recheck(Path(args.dir), _check_scope(_load(args.scope)),
                              Path(args.found) if args.found else None, verdicts,
                              args.secrets_scanned, args.audited,
                              Path(args.repo) if args.repo else None)
            result["sealed"] = args.seal is not None
            _write_private(Path(args.out), json.dumps(result, indent=2) + "\n")
            for kind in ("fixed", "still_open", "cannot_check", "not_rechecked"):
                print(f"{kind}: {len(result[kind])}")
            return 0
        if args.command == "suspects":
            for problem in _keep_suspects(Path(args.src), Path(args.dir),
                                          Path(args.leads) if args.leads else None):
                print(problem)
            return 0
        if args.command == "from-semgrep":
            counts = _from_semgrep(_load(args.json), _check_scope(_load(args.scope)),
                                   Path(args.out))
            for part_id, count in sorted(counts.items()):
                print(f"part {_piece(part_id)}: {count} leads")
            return 0
        if args.command.startswith("from-"):
            data = _load(args.json)
            if args.command == "from-secrets-scan":
                prefix, found = "secret", _from_secrets_scan(data)
            elif args.command == "from-osv-scanner":
                if args.exit not in (0, 1):
                    # A failed run (no database offline, a file it can't read) still prints
                    # {"results": []}, which would read as a clean lockfile.
                    raise _Malformed(f"OSV-Scanner exited {args.exit}, so it didn't scan")
                prefix, found = "dep", _from_osv_scanner(data, args.lockfile or "lockfile")
            elif args.command == "from-npm-audit":
                prefix, found = "dep", _from_npm_audit(data, args.lockfile or "package-lock.json")
            else:
                prefix, found = "dep", _from_composer_audit(data,
                                                           args.lockfile or "composer.lock")
            _save(Path(args.out), prefix, found)
            return 0
        if args.command == "inventory":
            text = Path(args.blocks).read_text(encoding="utf-8")
            earlier_file = Path(args.dir) / "inventory.md"
            earlier = earlier_file.read_text(encoding="utf-8") if earlier_file.is_file() else ""
            _write_private(earlier_file, _inventory(text, earlier))
            return 0
        if args.command == "dedupe":
            repo = Path(args.repo) if args.repo else None
            _check_seal(Path(args.audit), args.seal, whole=False)
            for name in _dedupe(Path(args.new), Path(args.audit), repo):
                print(f"dropped {_piece(name)}: already reported")
            return 0
        _check_seal(Path(args.dir), args.seal, whole=False)
        meta = _check_meta(_load(args.meta)) if args.meta else None
        scope = _check_scope(_load(args.scope)) if args.scope else None
        recheck = _check_recheck(_load(args.recheck)) if args.recheck else None
        _write_private(Path(args.dir) / "REPORT.md",
                       _report(Path(args.dir), meta, scope, recheck,
                               sealed=args.seal is not None))
        return 0
    except _Malformed as exc:
        print(f"error: {_error_text(exc)}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {_error_text(f'{exc.strerror}: {exc.filename}')}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"error: {_error_text(exc)}", file=sys.stderr)
        return 1
    except (TypeError, KeyError, AttributeError) as exc:
        print(f"error: unexpected input shape ({type(exc).__name__})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
