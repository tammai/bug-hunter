# 2026-11-06-l-live-targets
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-06-l-live-targets.md   (this feature's record for people)
Track: L   (sized up because: approach and safety model needed an interview; footprint: 14 files)
Risk: high   (secrets: test-account tokens; untrusted agent requests reach a live server)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-06
Base: c4ffa8d
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: ac40d11 tree a128ddbed53a956b892c9fc2945dde0534ba086b
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- scope.py tags integrations in _main via _calls_third_parties; route markers follow the same shape (scripts/scope.py:199)
- reuse stub_server.py's _redact_query/_redact_body/_has_secret for the proxy log (import from scripts/)
- targets.json lives next to the drafts folder: drafts.py drafts_dir(repo).parent (scripts/drafts.py:23)
- constitution III wording and PRD goals line are docs edits in task 4

## Tasks
1. **Live proxy** — AC-001 AC-002 AC-003 AC-004 AC-005
   - Files: `scripts/live_proxy.py`, `tests/test_live_proxy.py`
2. **Live scope** — AC-006
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_scope.py`
3. **Live draft check** — AC-007
   - Files: `scripts/drafts.py`, `tests/test_drafts.py`
4. **Edge list, command, agents, docs** — AC-008 AC-009
   - Files: `edge-inputs/live-http.md`, `commands/hunt.md`, `agents/bug-hunter.md`, `agents/repro-verifier.md`, `tests/test_plugin_files.py`, `README.md`, `docs/sdlc/constitution.md`, `docs/sdlc/prd.md`

## Public Surface
- scripts/live_proxy.py --repo --target --log --max-requests --rate --idle-exit — AC-001 AC-005
- scope.py --live — AC-006
- drafts.py check --repo <repo> --target <t> — AC-007
- /hunt --target <name> — AC-009
- ~/.bug-hunter/<host>/<owner>/<repo>/targets.json format — AC-001

## Gate log
- 2026-11-06 Stage 1: pass — plan approved by the user; AC-007 refined before the red step to check real account values, so invented bad tokens stay usable
- 2026-11-06 Stage 2: pass
- 2026-11-06 review: ran security and code high (Risk: high; Public Surface; L), self-chosen: L
- 2026-11-06 Stage 3: fail — security r1: S1 high, S2-S5; code high r1: C1-C5 high, C6-C8; S3/C4 and S4 rated high (break must-never-break lines); C9-C13 and S4 beyond headers tickets
- 2026-11-06 Stage 2: pass

## Deviations
- 2026-11-06 tests/test_plugin_files.py What: the every-stack edge-list test now allows live-http.md, and the constitution test expects version 1.2.0. Why: live-http is chosen by routes, not stack, like integrations; principle III was amended to 1.2.0 (approved in Define). Effect: both still fail on any other unnamed list or version.
- 2026-11-06 tests/test_scope.py, tests/test_drafts.py What: AC-007 refined before the red step: drafts.py check takes --repo and --target and checks the target's real account values instead of banning every literal Authorization value. Why: invented bad tokens are a needed edge input and agents never see real tokens. Effect: the CLI is check <file> --repo <repo> --target <t>.
- 2026-11-06 scripts/live_proxy.py What: load_target(repo, target) and BadTarget are shared with drafts.py. Why: the draft check needs the same allow-list rules and account values as the proxy, so both read targets.json one way. Effect: drafts.py imports live_proxy lazily inside check, since live_proxy imports drafts.
- 2026-11-06 scripts/live_proxy.py What: AC-002 exception: relayed responses mask every account value (and the part after the scheme, and cookie values) as <redacted>, swap the target's scheme://host for the proxy URL and its host for <target>, and ask the target for uncompressed bodies; the proxy adds no Server or Date of its own and keeps the target's Content-Length on HEAD. Why: security r1 S3 and code r1 C4 (a target echoing headers or its own URL handed tokens and the address to agents, breaking a must-never-break line), C2 (the proxy's own headers looked like the target's). Effect: responses are unchanged except for those values.
- 2026-11-06 scripts/live_proxy.py, commands/hunt.md What: --check validates the target and prints 'target ok: <name> (writes; accounts)' without listening; /hunt runs it before the cost question and starts the proxy only after the owner's yes, checks it with kill -0 before the verifiers and restarts it with the remaining budget. targets.json is now validated at start: header names, values without line breaks or non-Latin-1 characters (errors never echo a value), account names usable as shell names, URLs without user:password@. Method-override headers and _method on read-only targets get 403; non-ASCII paths get 400 before the budget; the .. check covers the path only. Why: security r1 S1, S2, S4, S5 and code r1 C5-C8, C14. Effect: one more proxy flag, --check.
- 2026-11-06 agents/bug-hunter.md, agents/repro-verifier.md, scripts/stacks.json, tests/* What: live repros export BASE and <ACCOUNT>_AUTH after the isolation prefix; route markers add chi (Get/Post/Route/Mount on a / path) and drop 'api.' so axios instances aren't routes; AC-006's framework coverage is tested across 11 frameworks. Why: code r1 C1 (isolate.py unsets *AUTH*; a prefix assignment isn't seen by the same command's expansion), C3. Effect: none beyond the fixes.

## Open questions
-
