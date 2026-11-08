"""Render a finding-v1 draft's Steps from its JSON, replay and classify an HTTP repro against
the rebuild and the reference, and write it as a contracts C6 file."""

import argparse
import hashlib
import importlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from drafts import expected_body, fenced, leaks, oracle_problems
from live_proxy import REFUSED_HEADER

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "contracts" / "v1"))
contracts = importlib.import_module("contracts")  # vendored: importable only after the insert

# Case-insensitive: on Windows and macOS `bh-0001.json` takes the name `BH-0001.json`.
FINDING_NAME = re.compile(r"^BH-(\d+)\.json$", re.I)
MAX_NUMBER = 999_999_999
SEVERITY = re.compile(r"^Severity:[ \t]*(\S+)[ \t]*$", re.M | re.I)
ENV_NAME = re.compile(r"`([A-Z][A-Z0-9_]*)`")
LEADING_BACKTICKS = re.compile(r" {0,3}(`+)")
STEPS_HEADING = "## Steps to reproduce"
WHERE = "## Repro (finding-v1)"
OBSERVED = "## Observed (finding-v1)"
PLAYWRIGHT_FILE = "bh-repro.spec.ts"
PLAYWRIGHT_END = "BH_TEST_END"
DEFECT = re.compile(r"^Defect:[ \t]*yes[ \t]*$", re.M | re.I)
DEPARTURE_ID = re.compile(r"D-[0-9]{3,12}")  # C5's D-<3+ digits>, bounded
LABEL = "repro"
MAX_MESSAGE = 500
SIDES = ("rebuild", "reference")


class BadDraft(ValueError):
    pass


def _sections(text: str) -> dict[str, str]:
    bodies: dict[str, list[str]] = {}
    current = None
    for line, in_fence in fenced(text.splitlines()):
        if line.startswith("## ") and not in_fence:
            current = line[3:].strip().rstrip(":").casefold()
            bodies.setdefault(current, [])
        elif current is not None:
            bodies[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in bodies.items()}


def _fenced_json(sections: dict[str, str], where: str):
    """The JSON in a section's one fenced block, or None when it holds none."""
    inner = [line for line, in_fence in fenced(sections[where[3:].casefold()].splitlines())
             if in_fence]
    try:
        return json.loads("\n".join(inner[1:-1])) if len(inner) >= 2 else None
    except ValueError:
        return None


def is_http(steps: list) -> bool:
    """A C4 HTTP replay (`{request, expect}` steps) rather than a cli `{command, stdout}` list."""
    return any(isinstance(step, dict) and "request" in step for step in steps)


def is_playwright(repro) -> bool:
    """A browser repro: one Playwright test file, `{"runner": "playwright", "test": …}`."""
    return isinstance(repro, dict)


def repro_steps(sections: dict[str, str]) -> list[dict] | dict:
    """The hunter's JSON repro: the source of the repro and of the draft's visible Steps."""
    if WHERE[3:].casefold() not in sections:
        raise BadDraft(f"missing {WHERE} (a fenced JSON list of steps)")
    steps = _fenced_json(sections, WHERE)
    if isinstance(steps, dict):
        if (set(steps) != {"runner", "test"} or steps["runner"] != "playwright"
                or not isinstance(steps["test"], str) or not steps["test"].strip()):
            raise BadDraft(f'{WHERE} is not {{"runner": "playwright", "test": <the test file>}}')
        if any(line.strip() == PLAYWRIGHT_END for line in steps["test"].split("\n")):
            raise BadDraft(f"{WHERE}: the test has a line {PLAYWRIGHT_END}, which ends its "
                           "heredoc in Steps")
        return steps
    if not isinstance(steps, list) or not steps:
        raise BadDraft(f"{WHERE} is not one fenced JSON list of steps")
    if is_http(steps):
        errors = [m for s, m in contracts._check_steps(steps, WHERE[3:]) if s == "error"]
        if errors:
            raise BadDraft(errors[0])
        return steps
    for n, step in enumerate(steps, 1):
        if (not isinstance(step, dict) or set(step) != {"command", "stdout"}
                or not all(isinstance(v, str) for v in step.values())
                or not step["command"].split("\n")[0].strip()):
            raise BadDraft(f"{WHERE} step {n} is not {{\"command\": <text>, \"stdout\": <text>}} "
                           "with a command on its first line")
        if step["command"].startswith("$ "):
            raise BadDraft(f"{WHERE} step {n}: its command starts with a `$ ` prompt")
    return steps


def result_problem(result) -> str | None:
    """Why a value isn't what `replay` prints, or None."""
    kind = result.get("result") if isinstance(result, dict) else None
    if kind == "fail":
        step = result.get("step")
        if (set(result) == {"result", "step", "message"} and isinstance(step, int)
                and not isinstance(step, bool) and step >= 1
                and isinstance(result["message"], str)):
            return None
    elif isinstance(kind, str) and (kind == "pass" or kind.startswith("not run: ")):
        if set(result) == {"result"}:
            return None
    return ('not {"result": "pass"}, {"result": "fail", "step": n, "message": …} or '
            '{"result": "not run: …"}')


def observed(sections: dict[str, str], reference_optional: bool = False) -> dict:
    """The hunter's captured results against the rebuild and the reference."""
    # A browser repro is also hunted without a reference: then only the rebuild ran.
    if OBSERVED[3:].casefold() not in sections:
        raise BadDraft(f"missing {OBSERVED} (the replay results against both targets)")
    found = _fenced_json(sections, OBSERVED)
    allowed = ({"rebuild"}, set(SIDES)) if reference_optional else (set(SIDES),)
    if not isinstance(found, dict) or set(found) not in allowed:
        wanted = "rebuild, and reference when one ran" if reference_optional \
            else "rebuild and reference"
        raise BadDraft(f"{OBSERVED} is not one fenced JSON object with {wanted}")
    for side in found:
        if result_problem(found[side]):
            raise BadDraft(f"{OBSERVED} {side}: {result_problem(found[side])}")
    return found


def _steps_block(steps: list[dict]) -> list[str]:
    body = []
    for step in steps:
        command = step["command"].split("\n")
        body += ["$ " + command[0], *command[1:]]
        if step["stdout"]:
            body += step["stdout"].removesuffix("\n").split("\n")
    return _fenced_block(body)


def _http_block(steps: list[dict], results: dict) -> list[str]:
    body = []
    for n, step in enumerate(steps, 1):
        request = step["request"]
        line = f"step {n}: {request['method']} {request['path']}"
        if "account" in request:
            line += f" as {request['account']}"
        if "json" in request:
            line += " " + json.dumps(request["json"], ensure_ascii=False)
        # ASCII escapes: a target's text never reaches a reader as control characters.
        body += [line, "  expect " + json.dumps(step["expect"])]
    for side, variable in zip(SIDES, ("BASE", "REF_BASE"), strict=True):
        body += [f'$ python3 finding_v1.py replay --draft <this draft> --base "${variable}"',
                 json.dumps(results[side])]
    return _fenced_block(body)


def _playwright_block(test: str, results: dict) -> list[str]:
    body = [f"$ cat > {PLAYWRIGHT_FILE} <<'{PLAYWRIGHT_END}'",
            *test.removesuffix("\n").split("\n"), PLAYWRIGHT_END]
    for side, variable in zip(SIDES, ("BASE", "REF_BASE"), strict=True):
        if side in results:
            body += [f'$ python3 browser.py run --test {PLAYWRIGHT_FILE} --base "${variable}"',
                     json.dumps(results[side])]
    return _fenced_block(body)


def _fenced_block(body: list[str]) -> list[str]:
    # Longer than any backtick run that opens a line of output, so the output can't close it.
    # splitlines: a lone `\r` in output becomes a line break when the draft is read back.
    longest = max((len(m[1]) for line in body for piece in line.splitlines()
                   if (m := LEADING_BACKTICKS.match(piece))), default=0)
    fence = "`" * max(3, longest + 1)
    return [STEPS_HEADING, fence, *body, fence, ""]


def _replace_section(text: str, heading: str, body: list[str]) -> str:
    """The text with one section's body replaced; the section must exist."""
    lines = text.split("\n")
    headings = [i for i, (line, in_fence) in enumerate(fenced(lines))
                if line.startswith("## ") and not in_fence]
    start = next(i for i in headings
                 if lines[i][3:].strip().rstrip(":").casefold() == heading[3:].casefold())
    end = next((i for i in headings if i > start), len(lines))
    return "\n".join(lines[:start + 1] + body + lines[end:])


def render(text: str, results: dict | None = None) -> str:
    """The draft with its Steps section replaced by one block written from its JSON steps."""
    sections = _sections(text)
    steps = repro_steps(sections)
    if results is not None and (is_http(steps) or is_playwright(steps)):
        text = _replace_section(text, OBSERVED, ["```json", json.dumps(results), "```", ""])
    if is_playwright(steps):
        block = _playwright_block(steps["test"],
                                  results or observed(sections, reference_optional=True))
    elif is_http(steps):
        block = _http_block(steps, results or observed(sections))
    else:
        block = _steps_block(steps)
    lines = text.split("\n")
    headings = [i for i, (line, in_fence) in enumerate(fenced(lines))
                if line.startswith("## ") and not in_fence]
    names = {i: lines[i][3:].strip().rstrip(":").casefold() for i in headings}
    steps_at = [i for i in headings if names[i] == STEPS_HEADING[3:].casefold()]
    if len(steps_at) > 1:
        raise BadDraft(f"more than one {STEPS_HEADING}; the Repro section is the only repro")
    start = steps_at[0] if steps_at else None
    if start is None:
        start = end = next(i for i in headings if names[i] == WHERE[3:].casefold())
    else:
        end = next((i for i in headings if i > start), len(lines))
    return "\n".join(lines[:start] + block + lines[end:])


def finding(text: str) -> dict:
    """The finding for a draft, numbered BH-0001 until `write` gives it its number."""
    title = next((line for line in text.splitlines() if line.strip()), "")
    if not title.startswith("# ") or not title[2:].strip():
        raise BadDraft("missing a '# ' title line")
    header = text.split("\n## ", 1)[0]  # the lines under the title, before the first section
    severity = SEVERITY.search(header)
    if not severity or severity[1].lower() not in ("high", "medium", "low"):
        raise BadDraft("missing a 'Severity: high|medium|low' line under the title")
    sections = _sections(text)
    if not sections.get("what happens"):
        raise BadDraft("missing ## What happens")
    steps = repro_steps(sections)
    if is_playwright(steps):
        accounts = re.findall(r"\bACCEPT_ACCOUNT_[A-Z][A-Z0-9_]*\b", steps["test"])
        repro = {"runner": "playwright", "test": steps["test"],
                 "env": ["ACCEPT_BASE_URL", *dict.fromkeys(accounts)]}
    elif is_http(steps):
        accounts = [f"ACCEPT_ACCOUNT_{s['request']['account']}" for s in steps
                    if "account" in s["request"]]
        repro = {"runner": "http", "steps": steps,
                 "env": ["ACCEPT_BASE_URL", *dict.fromkeys(accounts)]}
    else:
        repro = {"runner": "cli", "steps": steps}
        setup = next((line for line in header.splitlines()
                      if line.strip().lower().startswith("set before running:")), None)
        if setup:
            repro["env"] = ENV_NAME.findall(setup)
    return {
        "id": "BH-0001",
        "source": "bug-hunter",
        "class": "build-defect",
        "severity": severity[1].lower(),
        "criterion": None,
        "rule": None,
        "repro": repro,
        "observed": {"rebuild": sections["what happens"], "reference": "not run: no --reference"},
        "route": "sdlc",
        "verified_by": {"agent": "repro-verifier", "result": "reproduced"},
        "title": title[2:].strip(),
        "draft": render(text),
    }


def classify_by_oracle(record: dict, text: str, spec: Path) -> dict:
    """Set class, criterion, rule and route from what Expected cites (spec §B1, without B2)."""
    from oracle import CRITERION, BadOracle, cited_rules, domain_headings, is_spec_gap

    try:
        problems = oracle_problems(text, spec)
    except BadOracle as exc:
        raise BadDraft(str(exc)) from None
    if problems:
        raise BadDraft(problems[0])
    if is_spec_gap(text):
        return {**record, "class": "spec-gap", "route": "rspec"}
    expected = expected_body(text)
    ids = CRITERION.findall(expected)
    rules = cited_rules(expected, domain_headings(spec))
    return {**record, "criterion": ids[0] if ids else None,
            "rule": f"domain.md §{rules[0]}" if rules and not ids else None}


class _SameBase(urllib.request.HTTPRedirectHandler):
    """Follow a redirect, as `contracts.py run-http` does, but only within the base."""

    def __init__(self, base: str):
        self.base = urlsplit(base.rstrip("/") + "/")

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = urlsplit(newurl)
        if (new.scheme, new.netloc) != (self.base.scheme, self.base.netloc) \
                or not (new.path + "/").startswith(self.base.path):
            return None  # a Location may name any host: left as the step's status
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _Refused(Exception):
    pass


class _RefusalCheck(urllib.request.BaseHandler):
    """Raise on bug-hunter's proxy refusing a request, which `_run_steps` can't see."""

    handler_order = 400  # before urllib turns a 4xx or 5xx into an error

    def http_response(self, request, response):
        if response.headers.get(REFUSED_HEADER):
            try:
                error = str(json.loads(response.read().decode("utf-8")).get("error", ""))
            except (ValueError, AttributeError, OSError):
                error = ""
            response.close()
            raise _Refused(error[:200] or str(getattr(response, "status", "")))
        return response

    https_response = http_response


def replay(steps: list[dict], base: str, env: dict) -> dict:
    """Run C4 HTTP replay steps against one base, with contracts' own runner."""
    # contracts.py run-http itself can't serve: it wants a criterion ID, which reference
    # defects and spec gaps lack. No proxy from the environment: loopback stays on this machine.
    urllib.request.install_opener(urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _SameBase(base), _RefusalCheck()))
    try:
        contracts._run_steps(steps, LABEL, base, env)
    except _Refused as exc:
        return {"result": f"not run: the proxy refused a request: {exc}"}
    except contracts._Fail as exc:
        message = str(exc)
        # Anchored: the rest of the message holds values the target sent.
        step = re.match(rf"{LABEL} (step (\d+)(: request failed: )?.*)", message, re.S)
        if message.startswith("not run: "):
            return {"result": _bounded(message)}
        if not step or step[3]:
            return {"result": _bounded(f"not run: {message}")}
        return {"result": "fail", "step": int(step[2]), "message": _bounded(step[1])}
    return {"result": "pass"}


def _bounded(message: str) -> str:
    # The message carries the target's values. A cut one keeps a digest of the whole, so two
    # messages that differ only past the cut still differ when classify compares them.
    if len(message) <= MAX_MESSAGE:
        return message
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
    return f"{message[:MAX_MESSAGE - 32]}... (sha256 {digest})"


def _verdict(cls: str) -> dict:
    return {"class": cls, "route": contracts.ROUTES[cls]}


def classify(rebuild: dict, reference: dict, *, covered: bool, defect: bool,
             departure: str | None, alone: str) -> dict:
    """Class and route from a repro's results against the rebuild and the reference."""
    # covered: Expected cites a criterion or rule. defect: the verified `Defect: yes`, wrong by
    # the bug bar whatever the spec says; it tells a shared defect from a shared behaviour the
    # spec words differently. alone: the spec's class, for a reference that didn't run.
    if rebuild["result"] == "pass":
        # Only verified drafts get here, so a pass now means the runs disagree.
        return _verdict("flaky")
    if rebuild["result"] != "fail":
        # A refused or unreachable rebuild says nothing about the bug: the run's to retry.
        return _verdict("environment")
    if reference["result"] not in ("pass", "fail"):
        return _verdict(alone)
    # Same wrong: the same failing step with the same message. A generated value (an ID, a
    # time) in the message makes two equal defects differ and land on build-defect, the safe
    # side: a person looks at every build defect.
    same = reference["result"] == "fail" and \
        (reference["step"], reference["message"]) == (rebuild["step"], rebuild["message"])
    if not same:
        if departure:
            return {**_verdict("accepted-departure"), "departure": departure}
        return _verdict("build-defect")
    if covered and defect:
        # Proposed only: a person decides what goes into departures.yaml.
        return {**_verdict("build-defect"), "propose_departure": "reference-defect-not-copied"}
    if covered:
        return _verdict("spec-gap")
    if defect:
        return _verdict("reference-defect")
    raise BadDraft("the rebuild matches the reference and nothing says either is wrong: "
                   "not a finding")


def _observed_text(result: dict) -> str:
    return {"pass": "as expected"}.get(result["result"], result.get("message", result["result"]))


def with_reference(record: dict, text: str, oracle: Path | None, results: tuple[dict, dict],
                   departure: str | None = None) -> dict:
    """The record classified from its replay results against the rebuild and the reference."""
    from oracle import is_spec_gap

    if record["repro"]["runner"] not in ("http", "playwright"):
        raise BadDraft("--rebuild and --reference need an HTTP repro (a list of C4 steps) or "
                       "a playwright one")
    if departure is not None and not DEPARTURE_ID.fullmatch(departure):
        raise BadDraft("--departure must be a departure ID like D-004")
    header = text.split("\n## ", 1)[0]
    verdict = classify(*results, covered=oracle is not None and not is_spec_gap(text),
                       defect=bool(DEFECT.search(header)), departure=departure,
                       alone=record["class"])
    fresh = dict(zip(SIDES, results, strict=True))
    # The draft shows the results the class came from, not the hunter's earlier run.
    return {**record, **verdict, "draft": render(text, fresh),
            "observed": {side: _observed_text(r) for side, r in fresh.items()}}


def load_result(path: Path, flag: str) -> dict:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise BadDraft(f"{flag} is not JSON") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise BadDraft(f"{flag} can't be read ({type(exc).__name__})") from None
    if result_problem(result):
        raise BadDraft(f"{flag}: {result_problem(result)}")
    return result


def classified(text: str, oracle: Path | None = None,
               results: tuple[dict, dict] | None = None, departure: str | None = None) -> dict:
    """The draft's finding, classified by the spec and, given both results, the reference."""
    record = finding(text)
    if oracle is not None:
        record = classify_by_oracle(record, text, oracle)
    if results is not None:
        return with_reference(record, text, oracle, results, departure)
    if record["repro"]["runner"] == "http":
        raise BadDraft("an HTTP repro is written with --rebuild and --reference results")
    if departure is not None:
        raise BadDraft("--departure needs --rebuild and --reference results")
    return record


def _next_number(out: Path) -> int:
    # Compared by value; one too long to be ours counts as "full", so its name is never retried.
    digits = [m[1].lstrip("0") or "0" for p in out.iterdir() if (m := FINDING_NAME.match(p.name))]
    numbers = [int(d) if len(d) <= len(str(MAX_NUMBER)) else MAX_NUMBER + 1 for d in digits]
    number = max(numbers, default=0) + 1
    if number > MAX_NUMBER:
        raise BadDraft(f"--out already holds BH-{MAX_NUMBER}; use a new folder")
    return number


def write(repo: str, out: Path, draft: Path, oracle: Path | None = None,
          results: tuple[dict, dict] | None = None, departure: str | None = None,
          targets: tuple[tuple[dict, str], ...] = ()) -> Path:
    """`targets`: (target, its variable) whose hosts and logins the finding must not hold."""
    if out.resolve().is_relative_to(Path(repo).resolve()):
        raise BadDraft("--out is inside the repo; findings are written outside it")
    text = draft.read_text(encoding="utf-8")
    record = classified(text, oracle, results, departure)
    # The fresh results passed only the proxy's masking; this is the drafts' second check.
    # Only an HTTP repro's observed text comes from the targets; a cli draft's is the
    # hunter's own What happens, which the draft scan below covers.
    echoed = "\n".join(record["observed"].values()) if results is not None else ""
    for target, variable in targets:
        found = leaks(echoed, target, variable, replay=True)
        if found:
            # A target's own text, so nothing to rewrite: say what slipped through.
            raise BadDraft(f"the finding {found[0].split(':')[0]}: a target echoed it past "
                           "the proxy's masking")
        found = leaks(record["draft"], target, variable, replay=True)
        if found:
            raise BadDraft(f"the finding's draft {found[0]}")
    problems = [m for s, m in contracts.check_finding(record) if s != "warning"]
    if problems:
        raise BadDraft(f"not a valid finding-v1: {problems[0]}")
    out.mkdir(parents=True, exist_ok=True)
    record["id"] = f"BH-{_next_number(out):04d}"
    path = out / f"{record['id']}.json"
    try:
        with path.open("x", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except FileExistsError:
        raise BadDraft(f"{path.name} already exists in --out; nothing was overwritten") from None
    return path


def _main(argv: list[str] | None = None) -> int:
    # Windows Python before 3.15 writes in the ANSI code page; the commands read UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors=stream.errors)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("render", help="rewrite a draft's Steps from its Repro JSON, in place")
    r.add_argument("--draft", required=True, type=Path)
    w = sub.add_parser("write", help="write one verified draft as the next BH-NNNN.json")
    w.add_argument("--repo", required=True, help="the hunted repo; --out must be outside it")
    w.add_argument("--out", required=True, type=Path)
    w.add_argument("--draft", required=True, type=Path, help="a draft its verifier reproduced")
    w.add_argument("--oracle", type=Path, help="the spec folder: class from what Expected cites")
    w.add_argument("--target", help="the rebuild's target name: the finding may not show it")
    w.add_argument("--ref-target", help="the reference's target name: likewise")
    c = sub.add_parser("classify", help="print the class and route from both replay results")
    c.add_argument("--draft", required=True, type=Path)
    c.add_argument("--oracle", type=Path, help="the spec folder Expected cites")
    for sp in (w, c):
        sp.add_argument("--rebuild", type=Path, help="replay's output against the rebuild")
        sp.add_argument("--reference", type=Path, help="replay's output against the reference")
        sp.add_argument("--departure", help="the departure ID the difference matches")
    p = sub.add_parser("replay", help="run a draft's HTTP repro against one base")
    p.add_argument("--draft", required=True, type=Path)
    p.add_argument("--base", required=True, help="a proxy listener: $BASE or $REF_BASE")
    args = parser.parse_args(argv)
    try:
        results = None
        if args.command in ("write", "classify"):
            if args.command == "classify" and not (args.rebuild and args.reference):
                raise BadDraft("classify needs --rebuild and --reference")
            if bool(args.rebuild) != bool(args.reference):
                raise BadDraft("--rebuild and --reference go together")
            if args.rebuild:
                results = (load_result(args.rebuild, "--rebuild"),
                           load_result(args.reference, "--reference"))
        if args.command == "render":
            # The same checks as write, so a draft write would refuse never reaches a verifier.
            text = finding(args.draft.read_text(encoding="utf-8"))["draft"]
            args.draft.write_text(text, encoding="utf-8", newline="")
        elif args.command == "replay":
            steps = repro_steps(_sections(args.draft.read_text(encoding="utf-8")))
            if not is_http(steps):
                raise BadDraft("replay runs an HTTP repro (a list of C4 steps); "
                               "this draft's is not")
            # ASCII: the target's text must not reach a terminal as control characters.
            print(json.dumps(replay(steps, args.base, os.environ)))
        elif args.command == "classify":
            record = classified(args.draft.read_text(encoding="utf-8"), args.oracle, results,
                                args.departure)
            print(json.dumps({k: record[k] for k in ("class", "route", "departure",
                                                      "propose_departure") if k in record}))
        else:
            from live_proxy import BadTarget, load_target

            try:
                targets = tuple((load_target(args.repo, name), variable) for name, variable in (
                    (args.target, "BASE"), (args.ref_target, "REF_BASE")) if name)
            except BadTarget as exc:
                raise BadDraft(str(exc)) from None
            print(write(args.repo, args.out, args.draft, args.oracle, results,
                        args.departure, targets))
    except BadDraft as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot {args.command} the draft: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
