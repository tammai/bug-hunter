from pathlib import Path

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
