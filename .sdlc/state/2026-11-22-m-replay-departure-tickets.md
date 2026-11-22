# 2026-11-22-m-replay-departure-tickets
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-replay-departure-tickets.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 9 files)
Risk: high   (untrusted input: request paths and headers at the proxy that holds account tokens; result files and departures.yaml)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: fdd1072
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 7b99ff2 tree 026357f484dd9bfb934ed164244e6e48ff3f3cd3
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline in this session

## Handoff
- _leaves_base decodes once: scripts/live_proxy.py:257; only caller _forward at :543
- header filter: dropped set at scripts/live_proxy.py:401, applied in _send at :621; chosen account headers added after
- replay and contracts wording: scripts/finding_v1.py:323-342; _failed_value :423 moves into replay; matching_departure :455
- contracts/v1 is vendored byte-identical (vendor-check test): never edit it

## Tasks
1. **Proxy: decode to a fixpoint, header allow-list beside a second target** — AC-001 AC-002
   - Files: `scripts/live_proxy.py`, `tests/test_live_proxy.py`, `tests/test_reference.py`
2. **replay's structured check, opener restored, matching on check and runner** — AC-003 AC-004 AC-005 AC-006 AC-007 AC-010
   - Files: `scripts/finding_v1.py`, `tests/test_reference.py`, `tests/test_departures.py`, `tests/fixtures/reference-pair/drafts/departure.md`
3. **Registry: proposed-entry warning, ID digit bound** — AC-008 AC-009
   - Files: `scripts/finding_v1.py`, `tests/test_departures.py`
4. **Docs** — AC-002 AC-003
   - Files: `commands/hunt.md`, `CHANGELOG.md`

## Public Surface
- export `matching_departure(departures, repro, rebuild, criterion)` — AC-006
- command `finding_v1.py replay output gains optional check` — AC-003

## Test lock
- `tests/test_departures.py` sha256:af086864a612673ca3cbd5ee30b0b4c972dbc1bf280a8cec30d6c7684337131f
- `tests/test_live_proxy.py` sha256:b97876d814f30c382a8b03a0bb0dafa1410eba494f45904088753e1287412225
- `tests/test_reference.py` sha256:48aed01ae78852162b908c846edc88d57f2b711c490b564e0ea723974bc00a1d

## Gate log
- 2026-11-22 Stage 1: pass — plan approved by the owner (high-risk M)
- 2026-11-22 rebased onto origin/main fdd1072 (C3 and oracle merged), no conflicts; Base moved from 635113a
- 2026-11-22 Stage 2: pass
- 2026-11-22 review: ran security and code (Risk high; Public Surface changed), deferred by the owner to the end of all builds; r1 FAIL, r2 FAIL (owner allowed round 3), r3 PASS both; CHANGELOG written at Ship on the coordinator's instruction
- 2026-11-22 Stage 3: pass

## Deviations
- 2026-11-22 test-change tests/test_reference.py What: AC-002's test lists the routing header names itself instead of importing ROUTING_HEADERS; test_replay_reports_pass_fail_and_not_run expects the new check field on its failed value check Why: ROUTING_HEADERS is replaced by the allow-list BESIDE_ANOTHER; a failed equals check now carries check (AC-003)
- 2026-11-22 CHANGELOG.md What: not edited Why: owner instruction for parallel lanes (CHANGELOG conflicts); the entry is given in the report Effect: task 4 touches commands/hunt.md only
- 2026-11-22 tests/fixtures/reference-pair/drafts/departure.md What: unchanged Why: an Observed block without check stays valid; AC-010 asserts the check on the real replay output instead Effect: none
- 2026-11-22 scripts/live_proxy.py What: ROUTING_HEADERS removed, replaced by BESIDE_ANOTHER and a crosses() filter Why: the allow-list replaces the deny-list Effect: nothing else imported it
- 2026-11-22 matching_departure What: its second parameter is now the finding's repro (runner and steps) instead of the steps list, and it reads the result's check instead of parsing the message Why: R2-10 (runner from the record, not the steps' shape) and CR-4 Effect: its one caller, with_reference, passes record['repro']; tests updated
- 2026-11-22 test-change tests/test_reference.py What: AC-002's test also sends a request with only allow-listed headers plus Accept-Encoding and asserts its log entry has no note Why: accept-encoding (sent by urllib and every browser, and replaced by the proxy with identity) was logged as not forwarded on every request; it joins the allow-list (advisor check after the first commit)
- 2026-11-22 test-change tests/test_live_proxy.py tests/test_departures.py tests/test_reference.py What: review r1 fix tests added (dot-segment forms, bad departure IDs not echoed, departures command, check must fail the last check, nested JSON, replay nested body and bad --base); AC-002's test adds Sec-Route-Target (dropped) and Sec-CH-UA, Sec-GPC, Sec-WebSocket-Protocol (forwarded) Why: review round 1 S-1 S-2 S-3 S-4 S-5 S-6 CR-1 CR-3 L-2 L-3
- 2026-11-22 docs/sdlc/changes/2026-11-22-m-replay-departure-tickets.md What: AC-011 added (finding_v1.py departures) Why: review r1 CR-1 needs a new command, which the coordinator asked to add with its AC Effect: new public surface command finding_v1.py departures
- 2026-11-22 commands/hunt.md agents/bug-hunter.md README.md What: hunt.md runs finding_v1.py departures before the cost question, corrects the stated cause of an invalid registry at Classify, and lists held-back header names in the Report; bug-hunter.md tells hunters which headers cross beside a reference; README shows check and the allow-list Why: review r1 CR-1 CR-2 FP-2 FP-3 FP-4 Effect: docs only
- 2026-11-22 scripts/live_proxy.py scripts/finding_v1.py What: _leaves_base refuses dot-only segment names ending at ; ? # or with trailing dots/space and %u escapes; allow-list narrows sec- to sec-fetch-, sec-ch-, sec-websocket- and sec-gpc; departure IDs checked as ASCII D- plus 3-9 digits before contracts' checks; a check matches only when its value fails the last check; RecursionError and a bad --base give one line Why: review r1 S-1..S-6 CR-3 L-2 Effect: none beyond the fixes
- 2026-11-22 test-change tests/test_departures.py What: re-stamped after AC-011's first red run Why: AC-011 is new (review r1 CR-1); its red run was recorded with the departures branch of _main taken out, then put back
- 2026-11-22 test-change tests/test_departures.py tests/test_live_proxy.py What: review r2 fix tests added (nested registry, registry text escaped and bounded from every source, draft repro error escaped, either equals or rule fails, --oracle not a folder; overlong UTF-8, NUL and fullwidth dots in _leaves_base) Why: review round 2 R2-1 R2-2 R2-3 R2-4 S2-1 S2-2 S2-3 S2-6
- 2026-11-22 public surface: command finding_v1.py departures --oracle <spec> — AC-011 What: new command, named in README and run by commands/hunt.md before the cost question Why: review r1 CR-1, r2 R2-5 Effect: added to the public surface through this line
- 2026-11-22 scripts/finding_v1.py scripts/live_proxy.py commands/hunt.md agents/bug-hunter.md README.md What: one _printable helper escapes control and format characters and bounds every error and warning line; RecursionError around parse_yaml and check_departures; --oracle must be a folder; _fails true when either equals or rule fails; --base message matches its check; _leaves_base also refuses %c0/%c1, NUL and NFKC dots; docs FP-A FP-B FP-C FP-D Why: review round 2 R2-1 R2-2 R2-3 R2-4 R2-5 S2-1 S2-2 S2-3 S2-6 FP-3 Effect: none beyond the fixes
- 2026-11-22 test-change tests/test_live_proxy.py tests/test_departures.py What: r3 fix tests: 3- and 4-byte overlong UTF-8, F5-FF, mixed-depth spellings refused; valid UTF-8, CJK, emoji, Latin-1 %e9 kept; a ~990-deep equals is written whole or not at all Why: review r3 M3-1 M3-2 H3-1 (H3-1 confirmed: json.dump raised mid-write and left a partial BH-0001.json)
- 2026-11-22 scripts/live_proxy.py scripts/finding_v1.py commands/hunt.md What: _leaves_base checks each decode round as bytes (unquote_to_bytes) and refuses overlong lead patterns; write serializes before opening the file and _main catches RecursionError as one line; hunt.md header list says such as and points to bug-hunter.md Why: review r3 M3-1 M3-2 H3-1 L3-4 FP3-1 Effect: Public Surface line for finding_v1.py departures stays a deviation (state.py writes Public Surface only at new)

## Open questions
-
