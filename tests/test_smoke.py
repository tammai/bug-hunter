import json
import re
from pathlib import Path

from bug_hunter_version import version

MANIFESTS = Path(__file__).resolve().parent.parent / ".claude-plugin"


def test_version_matches_manifest():
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-rc\.\d+)?", version())


def test_marketplace_lists_the_plugin_at_the_manifest_version():
    plugin = json.loads((MANIFESTS / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((MANIFESTS / "marketplace.json").read_text(encoding="utf-8"))
    assert market["name"] == "bug-hunter"
    assert [(p["name"], p["source"], p["version"]) for p in market["plugins"]] == [
        ("bug-hunter", "./", plugin["version"])
    ]
