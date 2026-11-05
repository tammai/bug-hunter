"""List what hunters must not report again: the repo's open issues and earlier drafts."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from drafts import numbered, title


def _open_issues(repo: str) -> tuple[list[str], str | None]:
    """Lines for the open issues, or the reason they couldn't be listed."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--limit", "500", "--json", "number,title"],
            cwd=repo, capture_output=True, text=True, encoding="utf-8",
        )
    except FileNotFoundError:
        return [], "gh is not installed"
    if result.returncode != 0:
        reason = (result.stderr.strip().splitlines() or ["no message"])[0]
        return [], f"gh issue list failed: {reason}"
    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], "gh issue list printed something other than JSON"
    if not isinstance(issues, list) or not all(isinstance(i, dict) for i in issues):
        return [], "gh issue list printed an unexpected shape"
    return [f"- #{i.get('number', '?')} {i.get('title') or '(no title)'}" for i in issues], None


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("drafts_dir")
    args = parser.parse_args(argv)

    issues, why = _open_issues(args.repo)
    print("## Open issues")
    if why:
        print(f"Open issues: unavailable ({why}). Tell the owner duplicates can't be ruled out.")
    else:
        print("\n".join(issues) if issues else "- none")

    print("\n## Earlier findings")
    drafts = numbered(Path(args.drafts_dir))
    for _, path in drafts:
        print(f"- {path.stem} {title(path) or '(no title)'}")
    if not drafts:
        print("- none")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
