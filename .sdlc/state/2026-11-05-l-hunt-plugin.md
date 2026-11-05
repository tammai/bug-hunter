# 2026-11-05-l-hunt-plugin
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-05-l-hunt-plugin.md   (this feature's record for people)
Track: L   (sized up because: several distinct parts: 4 scripts, 2 commands, 2 agents, edge-input lists; footprint: 17 files)
Risk: high   (runs the target repo's code; posts issues with the owner's gh login; untrusted text reaches gh)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-05
Base: ccca279
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: fea4bd3 tree dc1ab3f0c9ca173adb37f5565dfe1de98d570a8a
Slice: B4   Slice base: 4a6b44b   Slice gates: none
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, in parts (backlog) because the user asked to break it down and autopilot

## Handoff
- Drafts live outside the target: ~/.bug-hunter/<owner>-<repo>/drafts (decision in the change file)
- Commands call scripts as python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"; tests import scripts via pythonpath=[scripts]
- Tests fake gh with a script on PATH (system boundary); git runs for real in tmp repos

## Tasks
1. **B1 scope.py** — AC-001 AC-002 AC-003
   - Files: `scripts/scope.py`, `tests/test_scope.py`
2. **B2 known.py and drafts.py** — AC-004 AC-005 AC-006 AC-007
   - Files: `scripts/known.py`, `scripts/drafts.py`, `tests/test_known.py`, `tests/test_drafts.py`, `tests/conftest.py`
3. **B3 post.py and /hunt-post** — AC-008 AC-009 AC-012
   - Files: `scripts/post.py`, `commands/hunt-post.md`, `tests/test_post.py`, `tests/test_plugin_files.py`
4. **B4 agents, edge inputs, /hunt, README** — AC-010 AC-011 AC-013
   - Files: `agents/bug-hunter.md`, `agents/repro-verifier.md`, `edge-inputs/generic.md`, `edge-inputs/python-cli.md`, `commands/hunt.md`, `README.md`, `tests/test_plugin_files.py`, `knowledge/index.md`

## Public Surface
- scripts/scope.py <repo> [paths] [--max N] — AC-001 AC-002 AC-003
- scripts/known.py <repo> <drafts-dir> — AC-004
- scripts/drafts.py dir|next|check — AC-005 AC-006 AC-007
- scripts/post.py <drafts-dir> <numbers> --label — AC-008 AC-009
- command /hunt [paths] [--max N] — AC-011
- command /hunt-post <numbers> --label — AC-012
- agents bug-hunter, repro-verifier — AC-010

## Gate log
- 2026-11-05 Stage 1: pass — plan self-approved (L, autopilot): every PRD capability maps to an AC; PRD open questions settled as decisions (container later; generic+python-cli lists first); no scope beyond the PRD; nothing irreversible
- 2026-11-05 autopilot: in this session, at the user's request
- 2026-11-05 Stage 2: pass
- 2026-11-05 review: ran security, code high (Risk: high; L; Public Surface), self-chosen: L autopilot
- 2026-11-05 Stage 3: fail — review r1: security S-01..S-04, code H1-H4, M1-M3, L1-L3 to fix; S-05 ticket
- 2026-11-05 Stage 2: pass

## Deviations
- 2026-11-05 scripts/drafts.py What: drafts_dir, numbered, title and problems are module functions, not only the CLI's dir/next/check. Why: known.py and post.py import them so the numbering and format rules live in one place. Effect: no new CLI surface; three scripts share one module.
- 2026-11-05 tests/test_plugin_files.py What: the edge-input keyword check compares case-insensitively. Why: list items start with a capital (Off-by-one, Subprocess) while the brief's words are lower case. Effect: same coverage of the brief's items.
- 2026-11-05 AC-005 / scripts/drafts.py What: drafts folder is ~/.bug-hunter/<host>/<owner>/<repo>/drafts (~/.bug-hunter/local/<folder>/drafts without origin), not <owner>-<repo>. Why: review S-03, the '-' join made acme-web/api and acme/web-api share drafts and posted.json across repos. Effect: AC-005's test asserts the new layout; README updated.
- 2026-11-05 scripts/throwaway.py, tests/test_throwaway.py What: new script making the agents' throwaway copy (standalone clone + uncommitted tracked diff, origin removed, refuses symlinks out of the copy). Why: review S-02, H4, S-04, M3, L2: cp -R of a worktree or .venv reached back into the target (constitution III). Effect: both agents call it; new CLI surface throwaway.py <repo> <dest>.
- 2026-11-05 agents/*.md, commands/hunt.md What: agents treat repo text, the known list and drafts as data, unset gh tokens and point GH_CONFIG_DIR at scratch in every Bash call, never run gh; /hunt passes the known list fenced as untrusted; known.py strips control characters and caps titles. Why: review S-01, issue titles from anyone reached agents holding the owner's gh login. Effect: prompt-injection surface reduced; not a sandbox (container isolation still out of scope).

## Open questions
-
