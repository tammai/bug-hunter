# 2026-11-08-m-oracle-scoping
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-08-m-oracle-scoping.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 11 files)
Risk: low
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-08
Base: 7e21c61
Owner: tammai.it@gmail.com
Tool: claude-code
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part

## Handoff
- Orchestrator answers Q1-Q6 are in the change file's Why (msg_e6417e8d9db0)
- Built on part 1 branch 2026-11-08-m-finding-v1-budget @ 7e21c61; contracts vendored there
- sdlc 3.x state: ## Criteria lines '- <ID> sha256:<hex>' (projects/sdlc scripts/state.py:130); spec-backed change file ACs '- **AC-003** → <ID>'

## Tasks
1. **oracle.py scope: feature parts, sources, ranking** — AC-001 AC-002 AC-005
   - Files: `scripts/oracle.py`, `tests/test_oracle.py`
2. **drafts.py check --oracle** — AC-003
   - Files: `scripts/drafts.py`, `tests/test_oracle.py`
3. **finding_v1.py write --oracle class mapping** — AC-004
   - Files: `scripts/finding_v1.py`, `tests/test_finding_v1.py`
4. **/hunt --oracle wiring, hunter and verifier briefs, docs** — AC-006
   - Files: `commands/hunt.md`, `agents/bug-hunter.md`, `agents/repro-verifier.md`, `README.md`, `CHANGELOG.md`

## Public Surface
- command `/hunt --oracle <spec>` — AC-006
- command `oracle.py scope` — AC-001
- command `drafts.py check --oracle` — AC-003
- command `finding_v1.py write --oracle` — AC-004

## Gate log
- 2026-11-08 Stage 1: pass — plan not stopped for approval: low-risk M; orchestrator answered Q1-Q6
- 2026-11-08 verify: only the 17 baselined Windows tests fail (diffed); AC-001..005 red then green; review: code-review medium (Public Surface not none), not asked: low risk
- 2026-11-08 Stage 2: pass — verify fails only on baselined tests
- 2026-11-08 round 1 fixes: F1-F7, F10 test first (test_oracle, test_finding_v1), F8/F9 cleaned while fixing; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — round 1 fixed
- 2026-11-08 round 2 decision A (msg_ea9882f3a307): R2-1..R2-5 fixed test first; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — round 2 fixed
- 2026-11-08 round 3 decision A (msg_5846ed272ed6): R3-1..R3-5 fixed test first (4 new tests); verify fails only on the 17 baselined (diffed)
- 2026-11-08 Stage 2: pass — round 3 fixed; waived as directed
- 2026-11-08 Stage 3: pass — review done; round 3 waived as directed; tests fail only on baselined

## Deviations
- 2026-11-08 scripts/oracle.py source files What: read from sdlc 3.x state files (## Criteria, ## Tasks) and change files citing → <ID>, not from change files' ## Tasks as B1 words it. Why: sdlc 3.x keeps Tasks in the state file; orchestrator approved (msg_e6417e8d9db0). Effect: same files B1 intends.
- 2026-11-08 Module exports build cited_rules domain_headings load_lock (scripts/oracle.py), classify_by_oracle and write's new oracle parameter (scripts/finding_v1.py) What: functions behind the CLIs, shared by drafts.py and finding_v1.py. Why: the surface lists the CLIs. Effect: none.
- 2026-11-08 BadOracle exception in scripts/oracle.py What: the error type drafts.py catches for a bad spec folder. Why: one error line, no traceback (AC-005). Effect: none.
- 2026-11-08 Round 1 helper exports rule_citations is_spec_gap (scripts/oracle.py), expected_body oracle_problems (scripts/drafts.py) What: one place for citation and spec-gap rules, used by drafts.py check and finding_v1.py write. Why: review round 1 (F1, F2, F4, F8). Effect: write --oracle refuses what check --oracle refuses.
- 2026-11-08 waived round 3: R3-1 R3-2 R3-3 R3-4 R3-5 — each a one-to-two-line fix in scripts/oracle.py proven by its own test, committed without a round-4 check, as the orchestrator directed (msg_5846ed272ed6). What: no re-review of these five fixes. Why: orchestrator decision. Effect: fixes are tested but not re-reviewed.

## Open questions
-
