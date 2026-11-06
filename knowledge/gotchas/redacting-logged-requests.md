---
type: gotcha
title: Redact logged requests by parsing and decoding, through one check
description: Why stub_server.py parses bodies, decodes escapes before matching secret words, and withholds what it can't make safe.
---

# Redacting logged requests

`scripts/stub_server.py` logs every request a hunter's code sends, and that log is pasted into drafts as evidence, so a secret in it gets published. Eight review rounds (2026-11-06) each found a new leak in the redaction until it followed these rules:

- **Parse the body in the shape it claims** (JSON whole, ndjson per line, forms and queries split on `&`, multipart with the `email` package) and replace secret-named fields. Matching patterns in raw text always misses a shape: bare JSON values, multi-line parts, keys with object values.
- **One secret check for everything**, `_has_secret`: names, values, headers, unparsed bodies and the partial body of a broken request. Each leak in rounds 4–6 was a path with its own weaker check (the malformed-body path, form values, the query).
- **Decode before matching, repeatedly:** `%xx` (nested: `%2574` → `%74` → `t`), `\uXXXX`, `\xXX`, `&#…;`, until nothing changes. Cap the passes and withhold if it is still changing. An encoded `=` (`%74oken%3Dabc`) hides a whole pair, so a piece is checked whole, not just its value.
- **Fail closed:** when redaction can't isolate a secret, the body is `<body withheld: N bytes>`, never the raw text. Only an unparsed body whose decoded text has no secret word is logged as is (the owner chose evidence over a blanket withhold on any escape).
- **What it can't catch:** a secret value with no secret word near it (`sk_live_…` in plain text). See [detecting-secrets-in-free-text.md](detecting-secrets-in-free-text.md) for why shape-guessing doesn't fix that.

## Masking what a live target echoes

`scripts/live_proxy.py` relays a dev or UAT server's responses to agents, and a target can echo the login it was sent (debug pages, echo routes, `Location`). Six review rounds (2026-11-06, live targets) settled on:

- **Keep tokens out of agents' hands first.** The proxy adds account headers itself, so masking is the second line, not the only one.
- **Mask the forms derived from each known value**, not secret-looking text: as is, JSON-escaped (with PHP's `\/`), percent-encoded (`quote`, `quote` keeping `/`, `quote_plus`, lower-case hex too), HTML entities (named, decimal, upper and lower hex), the decoded Basic `user:password` and the password alone, as UTF-8 and Latin-1 bytes.
- **Match exactly, not case-insensitively.** Ignoring case mangled every `Password` label for an account whose password was `password`; only percent hex needs both cases.
- **Mask hosts only where they stand alone**, and a dotless name (`uat`) only with its port, or `/actuator` becomes `/act<target>or`. The `:` lookbehind belongs to bare IPv6 hosts only.
- **Fail closed on what can't be checked:** a compressed body the target sent anyway gets 502, never relayed unmasked.
- **Validate `targets.json` at start without echoing values:** a header value with a newline made `http.client` raise an error whose traceback held the token.

The `fetch(` marker in `scripts/stacks.json` has the same lesson: a regex can't tell a call from a method definition in every layout. Each tweak moved a false negative somewhere else (ternaries, next-line braces), so it now skips only clear definitions and accepts an extra edge list for an untyped `fetch` method.
