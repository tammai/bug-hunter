# 2026-11-06-m-third-party-failures
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-06-m-third-party-failures.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 11 files)
Risk: low
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-06
Base: 36650f9
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 377bbb8 tree 02f70335a679d2842a704285ba068fcff47b302f
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- scope.py _tag has no repo path; tag integrations in _main like checklists (scripts/scope.py)
- Hunter Bash rules and installs live in agents/bug-hunter.md Hard rules; verifier step rules in agents/repro-verifier.md

## Tasks
1. **Stub server** — AC-001 AC-002
   - Files: `scripts/stub_server.py`, `tests/test_stub_server.py`
2. **Integrations tagging** — AC-003
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_stacks.py`
3. **Edge list and agents** — AC-004 AC-005
   - Files: `edge-inputs/integrations.md`, `agents/bug-hunter.md`, `agents/repro-verifier.md`, `tests/test_plugin_files.py`, `README.md`

## Public Surface
- scripts/stub_server.py --scenario <file> --log <file> — AC-001 AC-002
- scope.py edge_inputs value integrations — AC-003

## Gate log
- 2026-11-06 Stage 1: pass — plan not stopped for approval: low-risk M
- 2026-11-06 Stage 2: pass
- 2026-11-06 review: ran code default (Public Surface), not asked: low risk
- 2026-11-06 Stage 3: fail — code review r1 (built-in, medium): F7 high, F2-F6, F8-F10 bugs to fix; F1 resolved by release order
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — code review r2: R2-1 high, R2-2..R2-8 bugs; user chose round 3
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — code review r3: R3-1..R3-10 (4 high); user chose round 4: structured, fail-closed redaction
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — code review r4: R4-4 high, R4-1/3/5-9 bugs; user chose round 5
- 2026-11-06 Stage 2: pass

## Deviations
- 2026-11-06 tests/test_plugin_files.py What: the every-stack edge-list test now allows integrations.md next to generic.md. Why: integrations is chosen by what a part calls, not by its stack, so stacks.json names it in its own integrations block. Effect: the test still fails on any other unnamed list.
- 2026-11-06 scripts/stub_server.py, scripts/scope.py, scripts/stacks.json, agents/bug-hunter.md, commands/hunt.md, edge-inputs/integrations.md, tests/* What: review r1 fixes. Stub reads whole sized and chunked bodies (logs 64 KB plus body_bytes), redacts secret-named query, form and JSON fields (rewriting only when something was redacted), type-checks every scenario field at start, adds reset (RST) and truncate, scripted headers replace defaults, HEAD sends no body; hunters background the stub with output in stub.out and PID in stub.pid and stop it by PID; markers drop bare fetch( and webhook for global fetch, webhook handlers and signature checks, and add https.request, undici, XMLHttpRequest, http.client, URLSession, HttpURLConnection; marker search reads with errors=replace and only for kept parts; hunt.md wording. Why: built-in code review r1 F2-F10. Effect: F1 (pinned URL 404 before a release ships stub_server.py) is resolved by release order and recorded as a ticket.
- 2026-11-06 scripts/stub_server.py, scripts/stacks.json, agents/*.md, tests/* What: round 3. Secret-named fields redacted by pattern in any body (JSON, bare JSON values, form, multipart, ndjson, plain text, past 64 KB); the query keeps the client's raw encoding, only secret values replaced; booleans and non-finite numbers rejected at start; a malformed chunk size or Content-Length is logged with a note and answered 400; 1xx, 204 and 304 send no body; fetch markers skip def/function definitions and catch window/globalThis/self.fetch, bare verifySignature dropped; hunters keep stub files in a mktemp folder and wait for the listening line; the verifier saves and kills the stub's PID. Why: built-in code review r2 R2-1..R2-8. Effect: none beyond the fixes.
- 2026-11-06 scripts/stub_server.py, scripts/stacks.json, scripts/scope.py, agents/*.md, tests/* What: round 4 redesign at the user's request. Redaction is structured and fails closed: JSON and ndjson parsed whole (any secret-named key replaced whatever its type), forms and queries split with decoded names, multipart parsed with the email package; a secret-ish word left in a value, a body cut at 10 MB, or one that can't be parsed is logged as <body withheld: N bytes>. Delays capped at 3600 s, status 200-599, chunks over 64 MB malformed (bytes already read kept), 204/304 send no Content-Type/Length; --idle-exit (default 600 s) stops a forgotten stub; fetch( counts only in JS/TS files and not for method definitions; hunters write the scenario first, print the temp folder and stop waiting if the stub dies; the verifier no longer edits steps to save PIDs. Why: built-in code review r3 R3-1..R3-10. Effect: the round-3 test that the verifier saves stub.pid now only forbids kill %1.
- 2026-11-06 scripts/stub_server.py, scripts/stacks.json, agents/*.md, tests/* What: round 5. A redaction that decides to withhold always withholds; only a body that isn't in its claimed shape may be logged raw, and only with no secret word and no \\u or %xx escapes; --idle-exit waits for in-flight responses; chunk sizes must be plain hex (negative refused); the fetch( marker skips definitions with a return type or multi-line parameters; node-fetch restored; .mts, .cts and .html count as JS for markers, and .mts/.cts join the node stack's file types so those files are hunted at all; drafts start the stub on a fixed port and wait for it; the verifier's stale stub note removed; SECRET_HEADER alias removed. Why: built-in code review r4 R4-1, R4-3..R4-9. Effect: R4-2 (v0.2.0's stub lacks --idle-exit) needs no flag now, since drafts rely on the 600 s default from v0.3.0.

## Open questions
-
