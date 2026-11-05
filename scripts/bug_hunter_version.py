"""Plugin version, read from the plugin manifest."""

import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"


def version() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


if __name__ == "__main__":
    print(version())
