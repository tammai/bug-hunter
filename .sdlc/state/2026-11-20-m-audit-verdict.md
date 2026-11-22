# 2026-11-20-m-audit-verdict
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-20-m-audit-verdict.md   (this feature's record for people)
Track: L   (sized up because: several distinct parts: verdict, re-check/fixed tracking, accepted findings, Worth a look, OWASP, scope gaps, prompts; footprint: 12 files)
Risk: high   (secrets and PII in audit output; deploy go/no-go)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-20
Base: f72be3d
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: f72be3d tree 118791b35564f99e0e2972e1a5d717f934309ca9
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- findings.py _report builds REPORT.md: scripts/findings.py:406; dedupe key is category+CWE+root-cause path:line: scripts/findings.py:342
- checklist detection (vue via package.json dependency) to copy for react: scripts/scope.py:261, _depends_on at :197
- composer audit gives no fixed version (_from_composer_audit, scripts/findings.py:240); npm fixAvailable via _fix_text :194
- secrets_scan.py reads current files only, never git history: why committed secrets need a rotated line
- recurring defects: fingerprint-based secret checks, one-line CLI errors, no substring placeholder tests apply to every new output
- constitution amendment goes through sdlc:project-constitution (1.2.0 -> 1.3.0), not a hand edit

## Tasks
1. **Coverage facts in scope.py (react checklist, other_extensions, manifests without lockfile, dirty tree)** — AC-010
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_audit_scope.py`
2. **Verdict, gaps, accepted.md and OWASP table in findings.py report** — AC-001 AC-002 AC-003 AC-004 AC-009 AC-012
   - Files: `scripts/findings.py`, `scripts/owasp.json`, `tests/test_findings.py`
3. **Fixed tracking, stable identity and recheck command** — AC-005 AC-006 AC-007
   - Files: `scripts/findings.py`, `tests/test_findings.py`
4. **Worth a look: unconfirmed folder and report section** — AC-008 AC-012
   - Files: `scripts/findings.py`, `tests/test_findings.py`
5. **Prompts, constitution, README, PRD, CHANGELOG** — AC-011
   - Files: `commands/audit.md`, `agents/finding-verifier.md`, `docs/sdlc/constitution.md`, `docs/sdlc/prd.md`, `README.md`, `CHANGELOG.md`, `tests/test_plugin_files.py`

## Public Surface
- command `findings.py recheck` — AC-007
- config `accepted.md` — AC-004
- config `scope.py coverage fields` — AC-010

## Test lock
- `tests/test_audit_scope.py` sha256:380059db5c5a70cb1b1fd9d60386cf46f2782e8d582b86085cea00c1a19cc883
- `tests/test_findings.py` sha256:ab4a85b4702c2ab8a6872edb51bbcb61a5643076098d802f34c7b480b2cbc4b3
- `tests/test_plugin_files.py` sha256:574dd9bb6a9eb3a99d061f520c2b136f3d55c8df37c91533fc1dffb957749d5d

## Gate log
- 2026-11-20 Design approved by the user in brainstorming (2026-11-20). User asked to stop before Build: Define written, not advanced; resume with /sdlc:start to approve ACs and build.
- 2026-11-22 plan approved by the owner (high-risk L, stopped at the owner's request)
- 2026-11-22 Stage 1: pass — plan approved by the owner (high-risk L)
- 2026-11-22 Stage 2: pass
- 2026-11-22 review: ran security + code (Risk: high; L with public surface), self-chosen: L
- 2026-11-22 Stage 2: pass
- 2026-11-22 Review cap: owner chose one more fix round after round 2 (N1/SR2-0)
- 2026-11-22 Stage 2: pass
- 2026-11-22 Stage 2: pass
- 2026-11-22 Stage 3: pass

## Deviations
- 2026-11-22 Base What: moved from 51b6b35 to f72be3d. Why: main gained C1 (PR #42), the token-refresh release and planning commits since Define. Effect: diff and drift checks cover only this change.
- 2026-11-22 scripts/secrets_scan.py What: new --id-key option: each finding gets an HMAC-SHA256 id (16 hex) keyed with a random 32-byte key made 0600 at ~/.bug-hunter/<host>/<owner>/<repo>/secret-id.key. Why: the approved identity 'a secret by path plus its fingerprint' needs a per-finding fingerprint the scan didn't emit; a plain hash would be guessable, a keyed one isn't without the key (advisor). Effect: one more file touched; old findings without an id fall back to path, pattern and length.
- 2026-11-22 scripts/findings.py What: report reads scope.py's JSON (--scope) and recheck's JSON (--recheck) directly instead of facts the prompt copies into meta.json; a missing input or fact is a named gap. New subcommands earlier, recheck (named) and suspects; --scope - reads stdin. Why: fail closed, so a forgotten meta key can never read as Safe (advisor). Effect: meta.json keys are now policy, secrets_scanned, audited, audit_failures, check_failed.
- 2026-11-22 tests/test_findings.py tests/test_audit_scope.py tests/test_plugin_files.py What: existing tests updated: test_report_and_inventory uses the new meta and --scope; test_lockfiles_give_dependency_audit_steps expects each audit's lockfile; test_constitution_prd_and_readme_cover_audit expects 1.3.0. Why: the report's meta contract and the audits' shape changed by design. Effect: same assertions on the new shapes, none dropped.
- 2026-11-22 accepted.md expiry What: a past date is 'acceptance expired' (blocks again, listed), not 'invalid'; malformed, unknown-number and impossible dates are invalid. Why: AC-004 lists both readings; expired is the more useful message and accepts nothing either way. Effect: none on the verdict.
- 2026-11-22 test-change tests/test_findings.py What: review round 1: eleven new tests for the fixed classes (S1-S5, H1-H3, M1-M5, L1-L3); AC-007's test gives its scope a paths limit so finding 04 is really left out. Why: M1 redefined 'outside this run's scope' as left out by paths or --max, so on a whole-repo run 04 is now re-checked. Effect: stricter; no assertion weakened.
- 2026-11-22 commands/audit.md What: the run folder is made in step 1 and scope.py runs once into RUN/scope.json; the sweep and its leftover question move before that; check gets --agent; the re-check mode line goes outside the fenced finding. Why: review round 1 (L6, S5, S7), and sweep --older-than 0 would otherwise delete this run's own folder. Effect: one scope for every step.
- 2026-11-22 Public surface What: also findings.py earlier, findings.py suspects, check --agent, report --scope/--recheck, secrets_scan.py --id-key and the secret-id.key file, and audit/.unconfirmed-refused.json. Why: needed by the verdict flow and review round 1. Effect: none beyond the change.
- 2026-11-22 test-change tests/test_findings.py What: review round 2: new tests for severity raised on re-finding (N1/SR2-0), a gone lockfile fixed (N5), a never-committed local secret fixed with --repo (SR2-4), literal pathspecs (SR2-3), normalised and moved-back locations plus a NUL (N6, N7, SR2-7); the pose test adds an indented marker and a form feed (N2/SR2-1); the malformed-scope test adds dirty 1 and 0 (N3). Why: round 2 findings. Effect: stricter.
- 2026-11-22 Decisions What: an advisory whose lockfile is gone from the repo is fixed ('its lockfile X is gone from the repo'); one left out by paths or --max is not re-checked; one present but not audited is CANNOT CHECK. A finding found again at a higher severity gets a 'severity now X' status line and is ranked on it. Why: review round 2 (N5, N1/SR2-0); the change file's Decisions say a scripted finding the scripts don't produce again is fixed, and a secret counts as written by the scan. Effect: no evidence rewritten, numbers kept.
- 2026-11-22 test-change tests/test_findings.py What: review round 3: five new tests: an advisory never fixed while its lockfile may still ship (R3-1, R3-2/SR3-1), an unreadable location is CANNOT CHECK (R3-4), scan names can't forge evidence lines (SR3-0), history ignores an inherited GIT_DIR (SR3-2), recheck results carry no control characters (SR3-5). Why: round 3 findings, fixed without another round as both reviews passed. Effect: stricter.
- 2026-11-22 scripts/scope.py scripts/findings.py What: both import throwaway._REPO_VARS so the git calls this change added drop inherited GIT_DIR and the like. Why: SR3-2; one list of these variables. Effect: the pre-existing git calls in scope.py and secrets_scan.py are a ticket.

## Open questions
-
