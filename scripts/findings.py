"""Audit findings: format check, audit folder, converters from script output, and the report."""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from drafts import drafts_dir, numbered, title
from secrets_scan import (
    PATTERNS,
    SEVERITY_RANK,
    counts,
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
NPM_SEVERITY = {"critical": "critical", "high": "high", "moderate": "medium", "medium": "medium",
                "low": "low", "info": "low"}
INVENTORY_COLUMNS = ["field", "defined", "logged", "returned", "sent to", "stored", "deletion"]


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
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
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
    if evidence and not any(line.lstrip().startswith(("```", "~~~")) for line in evidence):
        found.append("## Evidence has no code block")
    for name in _secret_hits(text):
        found.append(f"contains what looks like a secret ({name}); write <redacted> instead")
    return found


def _write_private(path: Path, text: str) -> None:
    """Write atomically with mode 0600: audit output describes vulnerabilities."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".findings-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _Malformed(f"can't read {path} as JSON: {exc}") from exc


def _from_secrets_scan(data: object) -> list[str]:
    if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
        raise _Malformed("secrets scan output must be a JSON list of findings")
    found = []
    for item in data:
        try:
            path, line, name = str(item["path"]), int(item["line"]), str(item["pattern"])
            severity, committed = item["severity"], bool(item["committed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise _Malformed(f"secrets scan finding without {exc}") from exc
        if severity not in SEVERITIES:
            raise _Malformed(f"secrets scan severity {severity!r} isn't one of {SEVERITIES}")
        where = "committed to the repository" if committed else "in a local file, not committed"
        found.append(_render(
            f"Secret ({name}) {where}: {path}", severity, "secrets", "CWE-798", "proven",
            [f"`{path}:{line}`"],
            f"$ python3 scripts/secrets_scan.py <repo>\n{path}:{line} pattern={name} "
            f"length={item.get('length', '?')} committed={str(committed).lower()}",
            "Anyone with read access to the repository or its history can use this credential."
            if committed else
            "Only on this machine for now, but it's one `git add -A` from being committed.",
            "Rotate the credential, remove it (and from git history if committed), and load it "
            "from the environment or a secret manager.",
        ))
    return found


def _npm_finding(name: str, severity: str, title_text: str, cwe: str, advisory: str,
                 affected: str, fix: str, lockfile: str) -> str:
    return _render(
        f"Vulnerable dependency {name}: {title_text}", severity, "dependency", cwe, "advisory",
        [f"`{lockfile}:1` ({name} {affected})"],
        f"advisory: {advisory}\npackage: {name}\naffected: {affected}\nfix: {fix}",
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
        via = [v for v in vuln.get("via", []) if isinstance(v, dict)]
        first = via[0] if via else {}
        cwes = first.get("cwe") or []
        fix = vuln.get("fixAvailable")
        found.append(_npm_finding(
            str(vuln.get("name", name)), NPM_SEVERITY.get(vuln.get("severity"), "medium"),
            str(first.get("title") or f"through {', '.join(map(str, vuln.get('via', [])))}"),
            cwes[0] if isinstance(cwes, list) and cwes else "CWE-1395",
            str(first.get("url") or first.get("source") or "see npm audit"),
            str(vuln.get("range", "?")), _fix_text(str(vuln.get("name", name)), fix), lockfile))
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
            f"upgrade to {adv['patched_versions']}" if adv.get("patched_versions")
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


def _rows(lines: list[str], inside_only: bool) -> list[list[str]]:
    rows, inside = [], not inside_only
    for line in lines:
        if line.strip() == "=== PII INVENTORY ===":
            inside = True
            continue
        if line.strip().startswith("===") and inside_only:
            inside = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
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


def _key(text: str) -> tuple[str, str, str]:
    """What makes two findings the same: category, CWE and the root cause's path:line."""
    fields = _parse(text)[0]
    where = _where(text)
    root = next((w for w in where if "fix here" in w.lower()), where[-1] if where else "")
    spot = PATH_LINE.search(root)
    return fields.get("Category", ""), fields.get("CWE", ""), spot[0] if spot else root


def _merge_where(path: Path, extra: list[str]) -> None:
    """Add Where lines from a dropped duplicate to the finding that's kept."""
    lines = path.read_text(encoding="utf-8").splitlines()
    have = set(_where("\n".join(lines)))
    new = [line for line in extra if line not in have]
    start = end = None
    fence = False
    # Headings are found the way _parse finds them: outside code blocks, spacing ignored.
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
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


def _dedupe(new: Path, audit: Path) -> list[str]:
    """Drop new findings already in the audit folder, or repeated, keeping the most severe."""
    if new.resolve() == audit.resolve():
        raise _Malformed("dedupe needs two folders; given the same folder twice")
    seen_before = {_key(p.read_text(encoding="utf-8", errors="replace"))
                   for _, p in numbered(audit)}
    candidates = []
    for path in sorted(new.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        severity = _parse(text)[0].get("Severity", "low")
        candidates.append((SEVERITY_RANK.get(severity, 3), path.name, path, _key(text)))
    kept: dict[tuple[str, str, str], Path] = {}
    removed = []
    for _, _, path, key in sorted(candidates):
        if key in seen_before:
            path.unlink()
            removed.append(path.name)
        elif key in kept:
            _merge_where(kept[key], _where(path.read_text(encoding="utf-8", errors="replace")))
            path.unlink()
            removed.append(path.name)
        else:
            kept[key] = path
    return removed


def _report(folder: Path, meta: dict) -> str:
    good, skipped = [], []
    for number, path in numbered(folder):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _problems(text):
            skipped.append(path.name)
            continue
        fields, sections = _parse(text)
        where = next((PATH_LINE.search(line)[0] for line in sections["Where"]
                      if PATH_LINE.search(line)), "")
        good.append((SEVERITIES.index(fields["Severity"]), number, fields, title(path), where))
    good.sort(key=lambda g: (g[0], g[1]))

    out = ["# Security and PII audit", ""]
    if meta.get("policy"):
        out.append("Access policy: the owner's policy file was used.")
    else:
        out.append("No policy file was used: authorization findings that rest on an assumed "
                   "policy say so and are capped at medium.")
    out += ["", "## Findings", "", "| # | severity | category | proof | title | where |",
            "|---|---|---|---|---|---|"]
    for _, number, fields, head, where in good:
        out.append(f"| {number:02d} | {fields['Severity']} | {fields['Category']} | "
                   f"{fields['Proof']} | {head} | `{where}` |")
    out += ["", "## Counts", ""]
    for severity in SEVERITIES:
        out.append(f"- {severity}: {sum(1 for g in good if g[2]['Severity'] == severity)}")
    for category in CATEGORIES:
        count = sum(1 for g in good if g[2]["Category"] == category)
        if count:
            out.append(f"- {category}: {count}")
    inventory_file = folder / "inventory.md"
    if inventory_file.is_file():
        out += ["", "## PII inventory", "", inventory_file.read_text(encoding="utf-8").rstrip()]
    out += ["", "## Not confirmed (dropped)", ""]
    out += [f"- {d.get('title', '?')}: {d.get('reason', '?')}" for d in meta.get("dropped", [])]
    out += ["", "## Coverage", ""]
    out += [f"- Part not audited (--max): {p}" for p in meta.get("skipped_parts", [])]
    out += [f"- Dependencies not audited: {s}" for s in meta.get("not_audited", [])]
    out += [f"- Skipped, failed the format check: {name}" for name in skipped]
    return _scrub("\n".join(out)) + "\n"


def _check_meta(meta: object) -> dict:
    if not isinstance(meta, dict):
        raise _Malformed("--meta must be a JSON object")
    dropped = meta.get("dropped", [])
    if not isinstance(dropped, list) or not all(isinstance(d, dict) for d in dropped):
        raise _Malformed("--meta dropped must be a list of {title, reason} objects")
    for key in ("skipped_parts", "not_audited"):
        value = meta.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise _Malformed(f"--meta {key} must be a list of strings")
    return meta


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").add_argument("file")
    sub.add_parser("dir").add_argument("repo")
    sub.add_parser("next").add_argument("dir")
    sub.choices["check"].add_argument("--fingerprints")
    for name in ("from-secrets-scan", "from-npm-audit", "from-composer-audit"):
        p = sub.add_parser(name)
        p.add_argument("json")
        p.add_argument("out")
        p.add_argument("--lockfile")
    p = sub.add_parser("inventory")
    p.add_argument("blocks")
    p.add_argument("dir")
    p.add_argument("--fingerprints")
    p = sub.add_parser("dedupe")
    p.add_argument("new")
    p.add_argument("audit")
    p = sub.add_parser("report")
    p.add_argument("dir")
    p.add_argument("--meta")
    p.add_argument("--fingerprints")
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
            existing = numbered(Path(args.dir))
            print(f"{(existing[-1][0] if existing else 0) + 1:02d}")
            return 0
        if args.command.startswith("from-"):
            data = _load(args.json)
            if args.command == "from-secrets-scan":
                prefix, found = "secret", _from_secrets_scan(data)
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
            for name in _dedupe(Path(args.new), Path(args.audit)):
                print(f"dropped {name}: already reported")
            return 0
        meta = _check_meta(_load(args.meta) if args.meta else {})
        _write_private(Path(args.dir) / "REPORT.md", _report(Path(args.dir), meta))
        return 0
    except _Malformed as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc.strerror}: {exc.filename}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
