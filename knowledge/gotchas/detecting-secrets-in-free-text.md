---
type: gotcha
title: Don't guess secrets in free text; check against the ones you found
description: Why findings.py checks findings and reports against fingerprints of scanned secrets, not regex shapes.
---

# Detecting secrets in free text

`/audit` must never write a secret into a finding or `REPORT.md`, yet findings quote code. Six review rounds (2026-11-06) showed that guessing "is this a secret?" from shape can't work. Every rule tight enough to stop a leak, such as `NAME = value` or "a long base64 line", also rejects ordinary code (`password := r.FormValue(…)`, `key_size=1024`, hashes). Loosening it reopens a leak: JWTs have dots, AWS secrets start with `/`, weak passwords are all letters.

What works (`scripts/secrets_scan.py`, `scripts/findings.py`):

- **Known values.** The scan already finds the real values. It writes SHA-256 fingerprints of each value, of its 8-character slices (12 for single-case values) and of its key-body lines to the private scratch folder. `check`/`report`/`inventory` hash every position of the text against them. That's exact: no false alarms on code, and partly masked values are still caught.
- **Shapes only where code never looks like them:** vendor key prefixes (AWS, GitHub, Stripe, OpenAI, Anthropic, Slack, Google), JWTs, masked and cut-short keys after a known prefix, mixed-case base64 key-body lines.
- **Placeholders are whole-value only:** `<anything>`, `${…}`, an exact placeholder word, or a key prefix followed only by masking. A value that is *partly* masked (`Pass<redacted>`, `AKIAQ3J5…xxxx`) is real.
- **Don't fingerprint what prose is full of:** under 6 characters, numbers, booleans, URLs, lowercase paths, short letters-only words. Otherwise every finding at `file.js:1` fails.
- **Key bodies come in many layouts:** bare PEM, legacy encrypted (`Proc-Type:` lines and a blank line), one line with `\n` escapes (GCP JSON, `.env`), and quoted and joined in code (`"…\n" +`). A line that only *mentions* the BEGIN header mustn't swallow the rest of the file.
- **`/` is a base64 character:** a "starts with `/`, so it's a path" rule leaks secrets. Only lowercase path segments count as paths.

What it still can't catch: a secret the scan never saw that has no known shape. That relies on the agents writing `<redacted>`.

From [2026-11-06-l-security-pii-audit](../../docs/sdlc/changes/2026-11-06-l-security-pii-audit.md).
