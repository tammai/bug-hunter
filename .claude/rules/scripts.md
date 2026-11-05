---
paths:
  - "scripts/**/*"
  - "tests/**/*"
---

# Scripts rules

<!-- Tier 2: loads when touching the Python scripts and their tests. -->

- Standard library only, Python 3.12; no new dependencies — why: [constitution IV](../../docs/sdlc/constitution.md)
- Failing pytest first, covering the edge inputs we hunt for: spaces/non-ASCII paths, CRLF, empty input, missing JSON keys, subprocess failure.
- Scripts run as `python3 scripts/<name>.py` from the plugin folder; tests import them via `pythonpath = ["scripts"]`.
- Call `gh` and other tools with an argument list, never `shell=True`.
