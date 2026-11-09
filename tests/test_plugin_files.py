import json
import re
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
    assert files - named == {"generic", "integrations", "live-http"}
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
    assert "**Version**: 1.2.0" in constitution
    assert "traced" in constitution and "audit finding" in constitution.lower()
    prd = (ROOT / "docs/sdlc/prd.md").read_text(encoding="utf-8")
    goals, non_goals = prd.split("**Non-goals**")
    assert "security and PII" in goals
    assert "audit findings" in non_goals.split("## Core")[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "/audit" in readme and "policy.md" in readme


STUB_FETCH = ("curl -fsSLo stub_server.py "
              "https://raw.githubusercontent.com/tammai/bug-hunter/v")


def test_integrations_list_covers_failure_modes():
    text = (ROOT / "edge-inputs/integrations.md").read_text(encoding="utf-8").casefold()
    for item in ("timeout", "slow", "429", "retry-after", "5xx", "idempotent", "malformed",
                 "partial", "empty", "html", "expired token", "connection refused", "reset",
                 "duplicate", "out of order", "signature", "swallow", "pagination",
                 "stub_server.py"):
        assert item in text, item


def test_agents_use_the_stub_offline():
    _, hunter = read("agents/bug-hunter.md")
    for needed in ("<PLUGIN>/scripts/stub_server.py", "127.0.0.1", STUB_FETCH,
                   "never the real service", "stop the stub"):
        assert needed in hunter, needed
    _, verifier = read("agents/repro-verifier.md")
    assert STUB_FETCH in verifier and "<PLUGIN>/scripts/stub_server.py" in verifier


def test_stub_is_stopped_by_pid_and_hunt_names_integrations():
    _, hunter = read("agents/bug-hunter.md")
    assert "kill %1" not in hunter and "stub.pid" in hunter and "> " in hunter
    _, hunt = read("commands/hunt.md")
    assert "gets only the generic list" not in hunt and "integrations" in hunt


def test_stub_lifecycle_rules_in_both_agents():
    _, hunter = read("agents/bug-hunter.md")
    assert "mktemp -d" in hunter and "listening" in hunter
    _, verifier = read("agents/repro-verifier.md")
    assert "kill %1" not in verifier


def test_stub_start_and_stop_are_safe_as_written():
    _, hunter = read("agents/bug-hunter.md")
    assert hunter.index("$S/s.json") < hunter.index('--scenario "$S/s.json"')
    assert "kill -0" in hunter and 'echo "$S"' in hunter and "--idle-exit" in hunter
    _, verifier = read("agents/repro-verifier.md")
    assert "also save its PID" not in verifier and "--idle-exit" in verifier


def test_draft_stub_step_is_reachable_and_verifier_note_is_gone():
    _, hunter = read("agents/bug-hunter.md")
    assert "python3 stub_server.py --scenario s.json --log stub.log --port" in hunter
    assert "until grep -q listening stub.out" in hunter
    _, verifier = read("agents/repro-verifier.md")
    assert "may still be running" not in verifier


def test_draft_stub_uses_a_free_port_and_stops():
    _, hunter = read("agents/bug-hunter.md")
    assert "8765" not in hunter and "--port 0" in hunter
    assert "echo $! > stub.pid" in hunter and 'kill "$(cat stub.pid)"' in hunter
    assert "s/^listening on //p" in hunter


def test_draft_stub_prose_names_no_fixed_port():
    _, hunter = read("agents/bug-hunter.md")
    assert "fixed port" not in hunter


def test_command_and_agent_frontmatter_values_parse_as_written():
    # A plain YAML value can't start with an indicator or hold ": " / " #"; Claude Code then
    # drops the whole frontmatter (description, argument hint) without an error at runtime.
    bad = []
    for path in sorted([*ROOT.glob("commands/*.md"), *ROOT.glob("agents/*.md")]):
        meta, _ = read(path.relative_to(ROOT).as_posix())
        for key, value in meta.items():
            quoted = len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'"
            if not quoted and (value[:1] in "[]{},&*!|>%@`'\"#" or ": " in value
                               or " #" in value):
                bad.append(f"{path.name}: {key}")
    assert bad == []


def test_live_http_list_covers_edge_inputs():
    text = (ROOT / "edge-inputs" / "live-http.md").read_text(encoding="utf-8").lower()
    for topic in ("missing", "expired", "another account", "idor", "extra field", "wrong type",
                  "null", "malformed json", "content-type", "negative", "unicode", "long string",
                  "pagination", "double submit", "method", "trailing slash", "case",
                  "stack trace"):
        assert topic in text, topic


def test_hunt_target_flow_and_agent_rules():
    meta, hunt = read("commands/hunt.md")
    assert "--target" in meta.get("argument-hint", "")
    for needed in ("live_proxy.py", "scope.py", "--live", "targets.json", "writes",
                   "--max-requests", "--rate", "X-Bug-Hunter-Account", "$BASE",
                   "never the target URL", "--target", "drafts.py\" check"):
        assert needed in hunt, needed
    assert hunt.index("live_proxy.py") < hunt.index("Start N hunters?")
    _, hunter = read("agents/bug-hunter.md")
    _, verifier = read("agents/repro-verifier.md")
    for text in (hunter, verifier):
        for needed in ("<PROXY>", '"$BASE"', "_AUTH", "only the proxy"):
            assert needed in text, needed
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "--target" in readme and "targets.json" in readme


def test_live_steps_export_placeholders_and_keep_the_proxy_up():
    _, hunter = read("agents/bug-hunter.md")
    _, verifier = read("agents/repro-verifier.md")
    for text in (hunter, verifier):
        assert 'export BASE="<PROXY>"' in text
        assert not re.search(r'(?<!export )BASE="<PROXY>" BOB_AUTH=', text)
    _, hunt = read("commands/hunt.md")
    assert "--check" in hunt and "kill -0" in hunt
    assert hunt.index("--check") < hunt.index("Start N hunters?")
    intro = hunt.split("## Live target")[0]
    assert "--target" in intro


def test_hunt_and_audit_manage_their_run_folder():
    for rel in ("commands/hunt.md", "commands/audit.md"):
        _, body = read(rel)
        sweep = body.find('scripts/scratch.py" sweep')
        assert 0 <= sweep < body.find("## 2. Ask before spending"), rel
        assert 'RUN=$(python3 "$PLUGIN/scripts/scratch.py" new)' in body, rel
        assert 'scripts/throwaway.py" "$REPO" "$RUN/base"' in body, rel
        assert 'scripts/scratch.py" clean "$RUN"' in body, rel
        assert "freed" in body and "stop for any reason" in body, rel
        assert "RUN=<run>" in body or "`RUN`" in body, rel
        for gone in ("SCRATCH=$(mktemp -d)", 'rm -rf "$SCRATCH"', 'rm -rf "$RUN"'):
            assert gone not in body, f"{rel}: {gone}"


def test_hunt_saves_drafts_only_when_the_owner_chooses():
    _, hunt = read("commands/hunt.md")
    question = hunt.find("Fix these here, or save them as drafts to post?")
    assert question > 0
    assert hunt.find('scripts/drafts.py" next') > question
    assert 'mkdir -p "$DRAFTS"' not in hunt[:question]
    for needed in ("Fix here", "Save all", "Save some", "lost", "known list"):
        assert needed in hunt[question:], needed
    assert "--keep kept" in hunt


def test_agents_copy_from_the_base_share_the_cache_and_clean_up():
    for rel in ("agents/bug-hunter.md", "agents/repro-verifier.md",
                "agents/security-auditor.md", "agents/finding-verifier.md"):
        _, body = read(rel)
        assert ISOLATE_LINE in body, rel
        assert ('scripts/throwaway.py" "<REPO>" "<SCRATCH>/copy" --base "<RUN>/base"'
                in body), rel
        assert 'rm -rf "<SCRATCH>/copy" "<SCRATCH>/home"' in body, rel
        assert "(`RUN`)" in body, rel


def test_commands_stop_on_a_failed_run_folder_and_keep_the_proxy_in_it():
    for rel in ("commands/hunt.md", "commands/audit.md"):
        _, body = read(rel)
        new = body.index('RUN=$(python3 "$PLUGIN/scripts/scratch.py" new)')
        assert "non-zero exit" in body[new:new + 400], rel
    _, hunt = read("commands/hunt.md")
    assert 'P="$RUN/proxy"' in hunt and "P=$(mktemp -d)" not in hunt
    assert 'rm -rf "$P"' not in hunt
    assert "stop the proxy" in hunt[hunt.index("stop for any reason"):][:400]
    fix = hunt[hunt.index("- **Fix here:**"):][:600]
    assert "data" in fix and "throwaway copy" in fix
