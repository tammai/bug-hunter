# 2026-11-22-m-leak-scan-limits
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-leak-scan-limits.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 8 files)
Risk: high   (secrets and hosts leaking into public issues and to agents)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-22
Base: 06e2ea1
Owner: tam.mai@bigin.vn
Tool: claude-code
Current: Stage 2 – Build

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [ ] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- base is C3 at 06e2ea1 (branch 2026-11-22-m-leak-check-followups, unmerged): reuse _host_patterns, _ipv6_pattern tree, _holds_login
- masker: scripts/live_proxy.py _masker (341); live_proxy imports drafts at top, drafts imports live_proxy lazily
- message caps: finding_v1._bounded (345), browser._message (147)
- spec guard: oracle.build (216-224); _linked oracle.py:46, imported by finding_v1:401; scope._any_matches scope.py:246
- two masker test expectations change by decision: tests/test_live_proxy.py test_masks_hosts_only_where_they_stand_alone, test_masking_round_five_forms

## Tasks
1. **Shared address and link patterns, masker on them** — AC-001 AC-002 AC-003 AC-005 AC-008
   - Files: `scripts/drafts.py`, `scripts/live_proxy.py`, `tests/test_leak_scan_limits.py`, `tests/test_live_proxy.py`, `tests/test_drafts_scan_time.py`
2. **Message cut at a token boundary** — AC-004
   - Files: `scripts/finding_v1.py`, `scripts/browser.py`, `tests/test_leak_scan_limits.py`
3. **Spec folder and folder-link guards** — AC-006 AC-007
   - Files: `scripts/oracle.py`, `scripts/scope.py`, `tests/test_leak_scan_limits.py`
4. **Login shapes and cookie pieces** — AC-009 AC-010
   - Files: `scripts/drafts.py`, `tests/test_leak_scan_limits.py`, `tests/test_drafts_scan_time.py`

## Public Surface
- none

## Test lock
- `tests/test_leak_scan_limits.py` sha256:1cafddeaea5d520a21795bd0e1a2b67a2b92fc4b3ea2b08d2368e6155fa9f868

## Gate log
- 2026-11-22 Stage 1: pass — plan approved by the owner (high-risk M); question 1: (a) masker uses exactly the scan's patterns

## Deviations
- 2026-11-22 test-change tests/test_live_proxy.py test_masks_hosts_only_where_they_stand_alone What: 'xuat.acme.tests' now expects 'x<target>s'. Why: owner's answer (a) to question 1, the masker uses the scan's patterns with no left boundary. Fresh red: run against Base 06e2ea1 in a temporary worktree, fails there (not locked by this feature, so verify.py red --at doesn't apply).
- 2026-11-22 test-change tests/test_live_proxy.py test_masking_round_five_forms What: '2001:fd00::1' now expects '2001:<target>' and '::ffff:10.0.0.5' expects '<target>'. Why: owner's answer (a) to question 1; the mapped spelling is the same address. Fresh red: fails against Base 06e2ea1 in a temporary worktree.
- 2026-11-22 scripts/drafts.py What: new exported cut_whole(text, limit), used by finding_v1._bounded and browser._message; browser.py now imports drafts. Why: one shared cut rule for both caps (C4-8). Effect: one new public function; drafts imports only the stdlib, so no import cycle.
- 2026-11-22 tests/test_drafts_scan_time.py What: the linear-time test gains the new hostile shapes, a cookie account and a trailing-dot target, and a masker timing test (2 s bound per 50k run). Why: must-never-break line. Effect: measured 50k->200k ratios 2.8-4.2x on the new shapes (linear).

## Open questions
-
