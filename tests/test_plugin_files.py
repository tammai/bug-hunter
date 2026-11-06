import json
from pathlib import Path

from test_isolate import ISOLATE_LINE

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> tuple[dict[str, str], str]:
    """A plugin file's frontmatter (flat `key: value` lines) and its body."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{rel} has no frontmatter"
    head, body = text[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body


def test_hunt_post_files_only_through_post_script():
    meta, body = read("commands/hunt-post.md")
    assert meta.get("description") and meta.get("argument-hint")
    assert "scripts/post.py" in body
    assert "gh issue create" not in body
    assert "--label" in body


SECTIONS = ["What happens", "Steps to reproduce", "Expected", "Root cause"]


def test_agents_are_read_only_and_name_draft_sections():
    for rel in ("agents/bug-hunter.md", "agents/repro-verifier.md"):
        meta, body = read(rel)
        assert meta.get("name") and meta.get("description") and meta.get("tools"), rel
        tools = {t.strip() for t in meta["tools"].split(",")}
        assert not tools & {"Edit", "Write", "NotebookEdit", "MultiEdit"}, rel
        for section in SECTIONS:
            assert section in body, f"{rel} doesn't name {section}"
    _, verifier = read("agents/repro-verifier.md")
    assert "the draft alone" in verifier


def test_hunt_command_shows_cost_before_hunting():
    meta, body = read("commands/hunt.md")
    assert meta.get("description") and meta.get("argument-hint")
    assert "--max" in meta["argument-hint"]
    for needed in ("scripts/scope.py", "scripts/known.py", "scripts/drafts.py", "--max"):
        assert needed in body, needed
    assert body.index("est_tokens") < body.index("owner's yes")
    assert body.index("owner's yes") < body.index("bug-hunter:bug-hunter")
    assert body.index("bug-hunter:bug-hunter") < body.index("bug-hunter:repro-verifier")


def test_edge_input_lists_cover_the_brief():
    generic = (ROOT / "edge-inputs/generic.md").read_text(encoding="utf-8").casefold()
    for item in (
        "spaces", "non-ASCII", "Windows", "CRLF", "trailing", "empty", "bold", "code in table",
        "OAuth2", "off-by-one", "B10", "null", "subprocess", "encoding", "twice", ".DS_Store",
    ):
        assert item.casefold() in generic, item
    assert (ROOT / "edge-inputs/python-cli.md").read_text(encoding="utf-8").strip()


def test_agents_treat_input_as_data_and_work_in_a_throwaway_copy():
    for rel in ("agents/bug-hunter.md", "agents/repro-verifier.md"):
        _, body = read(rel)
        assert "data, never instructions" in body, rel
        assert ISOLATE_LINE in body, rel
        assert "scripts/throwaway.py" in body, rel
        assert "cp -R" not in body, rel
    _, hunt = read("commands/hunt.md")
    assert "untrusted" in hunt and "PLUGIN=" in hunt


def test_agents_keep_the_owners_git_credentials_out_of_reach():
    for rel in ("agents/bug-hunter.md", "agents/repro-verifier.md"):
        _, body = read(rel)
        assert "every Bash call" in body and "scripts/isolate.py" in body, rel
        assert "out of reach" not in body, rel
        assert "Cargo" in body, rel


TRAPS = {
    "node": ["undefined", "parseInt", "==", "floating", "time zone", "unhandled", "JSON.parse",
             "sort()"],
    "go": ["nil map", "loop variable", "shadow", "alias", "defer"],
    "rust": ["unwrap", "overflow", "as` cast", "UTF-8", "join"],
    "jvm": ["null", "==", "overflow", "time zone", "close"],
    "ruby": ["nil", "frozen", "Integer(", "encoding", "symbol"],
    "php": ["==", "empty(", "strpos", "array key", "json_decode"],
}


def test_every_stack_has_an_edge_input_list_covering_its_traps():
    stacks = json.loads((ROOT / "scripts/stacks.json").read_text(encoding="utf-8"))["stacks"]
    named = {s["edge_inputs"] for s in stacks}
    files = {p.stem for p in (ROOT / "edge-inputs").glob("*.md")}
    assert named <= files
    assert files - named == {"generic"}
    for name in named:
        assert (ROOT / f"edge-inputs/{name}.md").read_text(encoding="utf-8").strip(), name
    for name, traps in TRAPS.items():
        text = (ROOT / f"edge-inputs/{name}.md").read_text(encoding="utf-8").casefold()
        for trap in traps:
            assert trap.casefold() in text, f"{name}: {trap}"


def test_hunt_takes_edge_inputs_and_installs_from_scope():
    _, body = read("commands/hunt.md")
    assert "edge_inputs" in body and "installs" in body
    assert "when the part has `.py` files" not in body


def test_agents_allow_only_the_listed_locked_installs():
    for rel in ("agents/bug-hunter.md", "agents/repro-verifier.md"):
        _, body = read(rel)
        assert "only the exact commands in the `installs` list" in body, rel
        assert "its `step`, character for character" in body, rel
        assert "npm ci`)" not in body, rel
    _, verifier = read("agents/repro-verifier.md")
    assert "any other install" in verifier and "CANNOT RUN" in verifier


def test_audit_agents_are_read_only_isolated_and_adversarial():
    for rel in ("agents/security-auditor.md", "agents/finding-verifier.md"):
        meta, body = read(rel)
        assert meta.get("name") and meta.get("description") and meta.get("tools"), rel
        tools = {t.strip() for t in meta["tools"].split(",")}
        assert not tools & {"Edit", "Write", "NotebookEdit", "MultiEdit"}, rel
        assert ISOLATE_LINE in body and "scripts/throwaway.py" in body, rel
        for needed in ("proven", "traced", "advisory", "<redacted>", "policy.md",
                       "**Severity:**", "## Where", "## Evidence", "## Impact", "## Fix"):
            assert needed in body, f"{rel}: {needed}"
    _, auditor = read("agents/security-auditor.md")
    assert "at most 8 findings" in auditor and "=== PII INVENTORY ===" in auditor
    _, verifier = read("agents/finding-verifier.md")
    assert "the finding alone" in verifier and "disprove" in verifier
    for verdict in ("VERDICT: CONFIRMED", "VERDICT: NOT CONFIRMED", "VERDICT: CANNOT CHECK"):
        assert verdict in verifier


CHECKLIST_ITEMS = {
    "generic": ["IDOR", "role check", "SQL injection", "command injection", "path traversal",
                "SSRF", "secret", "rate limit", "CORS", "error", "critical", "high", "medium",
                "low"],
    "node": ["req.params", "middleware order", "prototype pollution", "alg", "eval(", "ReDoS"],
    "vue": ["v-html", "localStorage", "VITE_", "VUE_APP_", "open redirect", "route guard"],
    "pii": ["email", "phone", "national id", "payment card", "location", "health",
            "pii-logged", "pii-exposed", "pii-third-party", "pii-storage", "pii-retention"],
}


def test_security_checklists_cover_their_items():
    for name, items in CHECKLIST_ITEMS.items():
        text = (ROOT / f"security/{name}.md").read_text(encoding="utf-8").casefold()
        for item in items:
            assert item.casefold() in text, f"{name}: {item}"


def test_audit_command_asks_first_and_never_posts():
    meta, body = read("commands/audit.md")
    assert meta.get("description") and "--max" in meta.get("argument-hint", "")
    order = ["--focus security", "owner's yes", "scripts/throwaway.py", "scripts/secrets_scan.py",
             "from-secrets-scan", "from-npm-audit", "bug-hunter:security-auditor",
             "findings.py\" check", "bug-hunter:finding-verifier", "findings.py\" dedupe",
             "findings.py\" next", "findings.py\" inventory", "findings.py\" report"]
    positions = [body.index(marker) for marker in order]
    assert positions == sorted(positions)
    for banned in ("post.py", "gh issue", "gh api"):
        assert banned not in body, banned


def test_constitution_prd_and_readme_cover_audit():
    constitution = (ROOT / "docs/sdlc/constitution.md").read_text(encoding="utf-8")
    assert "**Version**: 1.1.0" in constitution
    assert "traced" in constitution and "audit finding" in constitution.lower()
    prd = (ROOT / "docs/sdlc/prd.md").read_text(encoding="utf-8")
    goals, non_goals = prd.split("**Non-goals**")
    assert "security and PII" in goals
    assert "audit findings" in non_goals.split("## Core")[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "/audit" in readme and "policy.md" in readme
