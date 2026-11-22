# 2026-11-22-m-isolate-followups
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-isolate-followups.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 3 files)
Risk: high   (secrets: agent isolation boundary; untrusted environment input)
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
inline in this session; the Windows-only checks (MSYS ssh with -F /dev/null) join the planned Windows session

## Handoff
- unset filter drops non-identifier names silently: scripts/isolate.py:258-261
- _refuse_links descriptor branch checks by path: scripts/isolate.py:346-352
- exports dict, where GIT_SSH_COMMAND and the stripped proxy values go: scripts/isolate.py:173-217
- isolated_env() dumps with compgen -e, which can't see non-identifier names: assert through a python child
- fail-closed decision (AC-004) waits on the owner's OK

## Tasks
1. **Isolation's own GIT_SSH_COMMAND** — AC-001 AC-002
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
2. **_refuse_links checks through its descriptor** — AC-003
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
3. **Fail closed on names bash can't unset** — AC-004 AC-005
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
4. **Proxy credentials stripped** — AC-006
   - Files: `scripts/isolate.py`, `tests/test_isolate.py`
5. **Gotcha doc** — AC-001
   - Files: `knowledge/gotchas/isolating-agents-without-a-sandbox.md`

## Public Surface
- env `GIT_SSH_COMMAND` — AC-001

## Test lock
- `tests/test_isolate.py` sha256:b714a5b583d720f949eb01f7949803cee1e7cbfb2cbe03381f8ee0e507a9cbae

## Gate log
- 2026-11-22 Stage 1: pass — plan approved by the owner (high-risk M)
- 2026-11-22 build done: verify PASS head 635113a tree 65feae28e3224a93f4f8c49644229d1b3744956b; review deferred by the owner to the end of the build (all lanes reviewed together); not advanced to Review

## Deviations
- 2026-11-22 tests/test_isolate.py AC-005 What: AC-005 shares AC-004's test (test_a_variable_bash_cant_unset_stops_isolation) instead of its own. Why: AC-005 guards behaviour that already holds, so a test of its own passes before the code and the red step refuses it. Effect: the change file's AC-005 row names AC-004's test; the check is unchanged.
- 2026-11-22 scripts/isolate.py proxy rule What: credentials are cut at the last @ anywhere after the scheme, not the last @ in the authority as the Decisions row says. Why: a raw / in a password would end the authority early and leave the password in the value. Effect: never leaks; an @ in a proxy URL's path (not seen in practice) would mis-route rather than leak.

## Open questions
-
