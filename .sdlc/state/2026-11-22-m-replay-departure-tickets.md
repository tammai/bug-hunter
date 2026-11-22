# 2026-11-22-m-replay-departure-tickets
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-replay-departure-tickets.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 9 files)
Risk: high   (untrusted input: request paths and headers at the proxy that holds account tokens; result files and departures.yaml)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: 635113a
Owner: tam.mai@bigin.vn
Tool: claude-code
Current: Stage 2 – Build

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [ ] 2 Build
- [ ] 3 Review   — the change file's ## Review
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

## Deviations
- 2026-11-22 test-change tests/test_reference.py What: AC-002's test lists the routing header names itself instead of importing ROUTING_HEADERS; test_replay_reports_pass_fail_and_not_run expects the new check field on its failed value check Why: ROUTING_HEADERS is replaced by the allow-list BESIDE_ANOTHER; a failed equals check now carries check (AC-003)
- 2026-11-22 CHANGELOG.md What: not edited Why: owner instruction for parallel lanes (CHANGELOG conflicts); the entry is given in the report Effect: task 4 touches commands/hunt.md only
- 2026-11-22 tests/fixtures/reference-pair/drafts/departure.md What: unchanged Why: an Observed block without check stays valid; AC-010 asserts the check on the real replay output instead Effect: none
- 2026-11-22 scripts/live_proxy.py What: ROUTING_HEADERS removed, replaced by BESIDE_ANOTHER and a crosses() filter Why: the allow-list replaces the deny-list Effect: nothing else imported it
- 2026-11-22 matching_departure What: its second parameter is now the finding's repro (runner and steps) instead of the steps list, and it reads the result's check instead of parsing the message Why: R2-10 (runner from the record, not the steps' shape) and CR-4 Effect: its one caller, with_reference, passes record['repro']; tests updated
- 2026-11-22 test-change tests/test_reference.py What: AC-002's test also sends a request with only allow-listed headers plus Accept-Encoding and asserts its log entry has no note Why: accept-encoding (sent by urllib and every browser, and replaced by the proxy with identity) was logged as not forwarded on every request; it joins the allow-list (advisor check after the first commit)

## Open questions
-
