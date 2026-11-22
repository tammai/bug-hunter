# 2026-11-22-m-leak-check-followups
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-leak-check-followups.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 2 files)
Risk: high   (secrets and hosts leaking into public issue drafts)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: 635113a
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 635113a tree fcfb9ff47b4eec1dbd5e0fdc236238c98f9a9caf
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- leak scan: scripts/drafts.py leaks (149), _holds_login (182), WORDLIKE (174), _spellings (217), _host_patterns (239); LOCAL_HOSTS in scripts/live_proxy.py:26
- word vs random: rare-pair constant generated from /usr/share/dict/words at 1e-4 frequency (measured in Define: 2% of random 10-letter tokens pass as words, 5% of dictionary words read random)
- regexes run on untrusted text: keep possessive runs; cap IPv6 run length; catch ValueError from ipaddress

## Tasks
1. **Login context and word test** — AC-001 AC-002
   - Files: `scripts/drafts.py`, `tests/test_drafts.py`
2. **Escapes and address spellings** — AC-003 AC-004 AC-005 AC-006 AC-007
   - Files: `scripts/drafts.py`, `tests/test_drafts.py`

## Public Surface
- none

## Test lock
- `tests/test_drafts.py` sha256:bdbf08c80e6ed74a51d7189d5c0e1900f81d265afd0ed3d9da95ce407ac46c03

## Gate log
- 2026-11-22 Stage 1: pass — plan approved by the user (high-risk M)
- 2026-11-22 Stage 2: pass
- 2026-11-22 Stage 3: fail — review r1: security FAIL S1-S4 (+S5), code FAIL C1-C4
- 2026-11-22 Stage 2: pass
- 2026-11-22 Stage 3: fail — review r2: code FAIL CR2-1..3, security FAIL R2-5; user chose one more fix round
- 2026-11-22 Stage 2: pass
- 2026-11-22 Stage 3: fail — review r3: security PASS, code FAIL CR3-1 CR3-2; user chose one more fix round
- 2026-11-22 Stage 2: pass

## Deviations
- 2026-11-22 AC-003 What: its target is http://ref with no port, not http://ref:3000. Why: a plain name with its port already matches anywhere, so the first test passed before the code; only the URL form shows the escape fix. Effect: same behaviour proved, change file updated before red was recorded.
- 2026-11-22 tests/test_drafts_scan_time.py What: new timing test for the must-never-break linear-scan line. Why: the first padded-zero patterns were quadratic on a long run of zeros (1.5 s for 10,000), found while timing hostile inputs; leading 0* now starts only at a run's first zero. Effect: one new test file.
- 2026-11-22 tests/test_drafts_leak_spellings.py What: new test file for review round 1 (S1-S5, C1-C4, C6, C9): mapped and zoned IPv6 targets, dotted IPv4 tails, a random token in any case, 'is:' and 'value is' prose, value only as a key, short loopback forms bounded, default port tied to the scheme. Why: tests/test_drafts.py is locked; new files are free. Effect: stricter, nothing weakened.
- 2026-11-22 scripts/drafts.py R6-2 What: IPv6 spellings come from an enumerating regex (every :: compression, zero-padding, a dotted IPv4 tail), not from parsing runs with ipaddress as the Decision said; scoped targets drop the zone; IPv4-mapped targets also get their IPv4 patterns. Why: parsing every suffix of a run is quadratic on a long hex-colon run; the regex is exact and linear. Effect: same spellings caught; review S9/C8.
- 2026-11-22 tests/test_drafts_scan_time.py What: the must-never-break 'about the same time as today' holds for letters and prose (about 2x base) but runs of '0:' or ':' scan about 9x slower than base, still linear (1 MB about 12 s against 1.3 s). Why: every position in such a run can start one of about 100 IPv6 spellings; a one-character lookahead already cut letter runs from 6x to 2x. Effect: the timing test bounds 50,000-character runs at 5 s, which a quadratic pattern would exceed by minutes.
- 2026-11-22 Review r1 code review What: ran as sdlc:code-reviewer, not the built-in code-review skill the flow names for M. Why: dispatched with the security review in one step. Effect: round 2 uses the built-in skill for the code check.
- 2026-11-22 scripts/drafts.py review round 3 What: IPv6 spellings render as one prefix-shared tree; a mapped target's IPv4 form keeps its scheme and port; port 80 adds http:// and ws:// without a port and 443 adds https:// and wss://, whatever the target's scheme; prose takes 'API key', 'secret key', 'access token'; a value element (<value>) counts; letters-only random tokens of any length match in any case. Why: round 2 CR2-1, CR2-2/R2-5, CR2-3, R2-6, R2-7, CR2-7. Effect: 1 MB of hostile '0:' or '::' now scans in about 1 s against 0.35 s on base (was 5.4 s against 0.78 s); still linear. Tests in tests/test_drafts_leak_spellings.py.
- 2026-11-22 scripts/drafts.py review round 4 What: the account's own placeholders are blanked before the anywhere-match of random tokens; a scheme may carry +-joined prefixes (git+http://); after is/was only spaces, a colon, quotes, backticks or a dash may stand before the value, and after a value key only spaces, quotes or [; ws and wss targets get default ports 80 and 443. Why: round 3 CR3-1, CR3-2/R3-2, CR3-3, R3-3. Effect: tests in tests/test_drafts_leak_spellings.py; timing unchanged.

## Open questions
-
