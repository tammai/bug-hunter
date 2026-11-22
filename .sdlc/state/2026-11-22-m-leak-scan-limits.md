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
- 2026-11-22 Stage 3 (run by the coordinator): fail — review r1: security FAIL SR1-1 SR1-2, code FAIL H1 M1 M2 M3 L1; C3 CR4-1 CR4-2 CR4-4 folded in; back in Build (state was still at Stage 2)
- 2026-11-22 review r1 tickets: SR1-5 (body cut before masking), SR1-6/L3 (sibling readers' folder-link guard), SR1-7 (.. in a spec path), C3 CR4-3 (placeholders of other accounts and non-WORDLIKE logins equal to the account name), CR4-5 (newline after 'is:')

## Deviations
- 2026-11-22 test-change tests/test_live_proxy.py test_masks_hosts_only_where_they_stand_alone What: 'xuat.acme.tests' now expects 'x<target>s'. Why: owner's answer (a) to question 1, the masker uses the scan's patterns with no left boundary. Fresh red: run against Base 06e2ea1 in a temporary worktree, fails there (not locked by this feature, so verify.py red --at doesn't apply).
- 2026-11-22 test-change tests/test_live_proxy.py test_masking_round_five_forms What: '2001:fd00::1' now expects '2001:<target>' and '::ffff:10.0.0.5' expects '<target>'. Why: owner's answer (a) to question 1; the mapped spelling is the same address. Fresh red: fails against Base 06e2ea1 in a temporary worktree.
- 2026-11-22 scripts/drafts.py What: new exported cut_whole(text, limit), used by finding_v1._bounded and browser._message; browser.py now imports drafts. Why: one shared cut rule for both caps (C4-8). Effect: one new public function; drafts imports only the stdlib, so no import cycle.
- 2026-11-22 tests/test_drafts_scan_time.py What: the linear-time test gains the new hostile shapes, a cookie account and a trailing-dot target, and a masker timing test (2 s bound per 50k run). Why: must-never-break line. Effect: measured 50k->200k ratios 2.8-4.2x on the new shapes (linear).
- 2026-11-22 scripts/drafts.py cookie pieces What: only word-shaped values (WORDLIKE) of non-session cookies are limited to credential context, and a value a session-like cookie also holds stays anywhere. Why: found after the first commit: a token-shaped value of an oddly named cookie (.AspNetCore.Cookies=CfDJ8...) had stopped counting anywhere, a leak Base caught. Narrower than the approved Cookies row, on the safe side. Effect: tests in tests/test_drafts_leak_spellings.py (outside this feature's test lock).
- 2026-11-22 scripts/finding_v1.py scripts/browser.py What: _bounded keeps a 'not run: ' prefix whole when it cuts; browser._message never returns empty (a placeholder line when the cut drops everything). Why: cut_whole can cut back to almost nothing, and readers test the 'not run: ' prefix and the message's truthiness. Effect: test in tests/test_drafts_leak_spellings.py.
- 2026-11-22 scripts/live_proxy.py What: a bare dotted or IP host with its port (uat.acme.test:8443) now masks as <target>:8443, not <target>. Why: the shared patterns match the host, not the netloc. Effect: the scan passes '<target>:8443', so nothing leaks; no test pinned the old output.
- 2026-11-22 C3 fold-in What: C3's review round-4 findings CR4-1 (scheme prefix misses ...http://localhost, endpoint.http://, -http://, 1.http://, an escaped slash before http://), CR4-2 (a value key allows only one [ and one quote) and CR4-4 (after is/was any non-word but sentence or line enders) are fixed in this change. Why: the owner's call; C3 ships first unchanged. Effect: scripts/drafts.py at() and _holds_login; tests in tests/test_leak_scan_r1.py.
- 2026-11-22 review r1 fixes What: browser.py no longer imports drafts and keeps its own copy of the cut rule (H1); its cut message carries a digest, and _first_failure returns the raw error so the new _failed checks NOT_THE_APP before any cut (L1). Why: browser.py is fetched and run alone. Effect: drafts.cut_whole is used by finding_v1 only.
- 2026-11-22 review r1 fixes What: the masker runs the str patterns on data decoded with surrogateescape and re-encodes (SR1-2); ZONE is any run up to the bracket, bounded at 64 (agrees in both); V6_END is ASCII (M1); an IPv6 target with a port also matches the port written unbracketed (SR1-1); _link_pattern refuses a following userinfo, bounded at 256 (SR1-4); alternatives sort by drafts._host (F5). Why: review r1. Effect: tests in tests/test_leak_scan_r1.py; 50k->200k timings 2.8-4x (linear).
- 2026-11-22 scripts/drafts.py cookie filter (M2/SR1-3) What: a non-session cookie's value is limited to credential context only when it has at most one rare letter pair (desktop has 'kt'), not when _reads_as_word holds as the relay suggested. Why: _reads_as_word('desktop') is False, so that rule would undo AC-010 (the ticket's own example); random values have many rare pairs (qwxzkvbnmt: 8). Effect: theme=qwxzkvbnmt and a 20-letter random value count anywhere again.
- 2026-11-22 M3 What: the value-first shape now skips up to three quoted attributes or keys, like the name-first one; unquoted HTML attributes (name=password type=text value=member) are put in the change file's Out of scope. Why: review r1 M3; the owner offered either. Effect: test in tests/test_leak_scan_r1.py.
- 2026-11-22 docs and change file What: change file (above Review) gains the L4 cost examples (1<target>, Domain=.<target>) and the unquoted-attributes Out of scope line; knowledge/gotchas/redacting-logged-requests.md and docs/sdlc/recurring-defects.md state the new masking rule (F3, F4); tests/test_live_proxy.py test renamed (F2), its assertions unchanged. Why: review r1. Effect: docs only; the r1 report files were written by the builder from the coordinator's relay because a hook blocked the reviewers' writes.

## Open questions
-
