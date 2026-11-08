# 2026-11-08-m-reference-classify
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-08-m-reference-classify.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 14 files)
Risk: high   (proxy holds account tokens; masking and isolation reshaped)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-08
Base: 8dcab0e
Owner: tammai.it@gmail.com
Tool: claude-code
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline: this session builds it, one part

## Handoff
- Orchestrator answers Q1-Q8 in the change file's Why (msg_d0c40199e049)
- Contracts 1.1.1 re-vendored from product-rebuild 3274d37 before Define (contracts/v1, README version line)
- Proxy handler state (budget, rate) lives in _handler today: scripts/live_proxy.py _handler; make it shared across two listeners
- contracts helpers reused: _check_steps, _pointer, _rule_ok, _same (contracts/v1/contracts.py:687,845,860,385)

## Tasks
1. **Re-vendor contracts 1.1.1** — AC-001
   - Files: `contracts/v1/CONTRACTS.md`, `contracts/v1/MANIFEST`, `contracts/v1/acceptance-manifest.schema.json`, `contracts/v1/contracts.py`, `contracts/v1/cost-line.schema.json`, `contracts/v1/criteria-lock.schema.json`, `contracts/v1/departures.schema.json`, `contracts/v1/finding.schema.json`, `contracts/v1/test_contracts.py`
2. **Two-target proxy** — AC-001 AC-002 AC-003
   - Files: `scripts/live_proxy.py`, `tests/test_reference.py`
3. **HTTP repro: replay, render, classify, write** — AC-004 AC-005 AC-006 AC-007
   - Files: `scripts/finding_v1.py`, `tests/test_reference.py`
4. **drafts.py check --reference** — AC-008
   - Files: `scripts/drafts.py`, `tests/test_reference.py`
5. **Fixture rebuild + reference pair** — AC-009
   - Files: `tests/fixtures/reference-pair/rebuild.py`, `tests/fixtures/reference-pair/reference.py`, `tests/fixtures/reference-pair/spec/criteria.lock.json`, `tests/fixtures/reference-pair/spec/domain.md`, `tests/fixtures/reference-pair/spec/departures.yaml`, `tests/fixtures/reference-pair/spec/features/F-TSK-01.md`, `tests/fixtures/reference-pair/spec/features/F-TSK-02.md`, `tests/fixtures/reference-pair/drafts/build-defect.md`, `tests/fixtures/reference-pair/drafts/reference-defect.md`, `tests/fixtures/reference-pair/drafts/spec-gap.md`, `tests/fixtures/reference-pair/drafts/departure.md`, `tests/test_reference.py`
6. **C:/Program Files/Git/hunt --reference wiring, prompts, docs** — AC-010
   - Files: `commands/hunt.md`, `agents/bug-hunter.md`, `agents/repro-verifier.md`, `README.md`, `CHANGELOG.md`

## Public Surface
- command `live_proxy.py --reference` — AC-001
- command `finding_v1.py replay` — AC-004
- command `finding_v1.py classify` — AC-006
- command `finding_v1.py write --rebuild --reference --departure` — AC-007
- command `drafts.py check --reference` — AC-008
- command `/hunt --reference` — AC-010

## Gate log
- 2026-11-08 Stage 1: pass — plan approved by the orchestrator (msg_d186240a8e49)
- 2026-11-08 verify: only the 17 baselined Windows tests fail (diffed against .sdlc/baseline.md); AC-001..009 red then green; review: code + security (risk high, Public Surface not none), approved by orchestrator (msg_d186240a8e49)
- 2026-11-08 Stage 2: pass — verify fails only on baselined tests
- 2026-11-08 round 1 fixes: S-1 S-2 S-3 S-4 S-6 S-7 S-8 S-9 and CR-1..CR-11 CR-13 CR-14 fixed test first; tickets S-5 (second scan of observed; length cap done), CR-12; first code-review call reviewed commit 8dcab0e (part 2) by mistake and was rerun on the working diff; verify fails only on the 17 baselined (diffed)
- 2026-11-08 Stage 2: pass — round 1 fixed; verify fails only on baselined tests
- 2026-11-08 round 2 fixes: S2-1 S2-2 S2-3 R2-1 R2-2 R2-4 R2-5 R2-6 R2-8 R2-11 R2-14 R2-15 fixed test first; verify fails only on the 17 baselined (diffed)
- 2026-11-08 Stage 2: pass — round 2 bugs fixed; verify fails only on baselined tests
- 2026-11-08 Stage 3: pass — security r2 PASS, code r2 PASS; tests fail only on baselined
- 2026-11-08 baseline waived at ship: the 17 failures are exactly the .sdlc/baseline.md rows (diffed after the last code change)

## Deviations
- 2026-11-08 scripts/finding_v1.py classify What: classification lives in finding_v1.py classify, not B2's 'findings.py classify'. Why: scripts/findings.py is /audit's findings script; orchestrator approved (Q4, msg_d0c40199e049). Effect: same behaviour, different file name.
- 2026-11-08 Module exports classify classified is_http load_result observed replay result_problem with_reference, and write's new results and departure parameters (scripts/finding_v1.py) What: functions behind the replay, classify and write CLIs; tests call classify directly for the table. Why: the surface lists the CLIs. Effect: none.
- 2026-11-08 scripts/live_proxy.py _place, _handler's label/shared/others parameters What: helpers for the second listener. Why: AC-001..003. Effect: single-target behaviour unchanged except the refusal header.
- 2026-11-08 scripts/finding_v1.py replay What: runs contracts' own _run_steps (installed opener: no environment proxy, redirects followed only within the base, proxy refusals raised) instead of its own step loop; a refusal reports no step number; messages cut at 500 characters. Why: review round 1 (S-2, S-9, CR-5, CR-6): same semantics as run-http, no copied rules. Effect: replay messages read 'step N ...' as before.
- 2026-11-08 scripts/finding_v1.py classify What: a rebuild replay that didn't run gives class environment (route orchestrator) instead of dropping the finding. Why: review round 1 CR-2; a verified finding must not be lost to a refused or stopped proxy. Effect: one more class beyond the B2 table, from C6's own list.
- 2026-11-08 scripts/live_proxy.py _masker What: one masker over both targets (union of secrets, each address to its own listener, longest first) with a right boundary on addresses (not followed by a word character, '-', or '.'/':' plus a word character); routing headers (X-Original-URL, X-Rewrite-URL, X-Forwarded-Host/-Prefix/-Path/-Server, Forwarded) dropped only with two targets; http.server's own errors carry the refusal header. Why: review round 1 S-1, S-3, S-7. Effect: single-target masking leaves an address followed by another port to the host pass (<target>:9443) instead of rewriting its prefix.
- 2026-11-08 tests/test_reference.py test_one_masker_covers_both_targets What: a review-fix test outside the AC table. Why: S-1's class (nested secrets, same host other port). Effect: none.
- 2026-11-08 scripts/finding_v1.py render What: takes optional results; with them the finding's draft shows those results in Observed and Steps. Why: review round 1 CR-3, one source of truth for class and draft. Effect: render --draft unchanged.
- 2026-11-08 Round 2 fixes What: replay keeps a sha256 digest when it cuts a message, anchors 'request failed' to contracts' own position; masker address boundary only blocks a longer host name (an address followed by a port is masked again, as on part 2) and keys addresses by bytes; four more routing headers dropped with two targets; http.server refusals logged; only the first listener's socket closed at exit; drafts.py hints name ACCEPT_ACCOUNT_<NAME> in reference mode; REFUSED_HEADER imported from live_proxy. Why: review round 2 (S2-1 S2-2 S2-3, R2-1 R2-2 R2-4 R2-5 R2-6 R2-8 R2-11 R2-14 R2-15). Effect: the round-1 single-target masking note no longer applies.
- 2026-11-08 Ship What: ship.py was denied by the Claude Code permission classifier ([External System Writes]); the commit c1a917d was made by hand (Status done via state.py, git add, git commit), no push, as the orchestrator's 'commit locally' allows. No Verified line: verify fails only on the 17 baselined Windows tests (diffed against .sdlc/baseline.md). Why: tool permission. Effect: ship.py's own verify rerun and Verified head/tree not recorded.

## Open questions
-
