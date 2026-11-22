# 2026-11-22-m-oracle-tickets
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-22-m-oracle-tickets.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 7 files)
Risk: low   (untrusted spec and repo history, but every file read stays behind _inside/_read and git paths are filtered by tracked; no new read path)
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
inline

## Handoff
- contracts.criterion_text_sha256 and CRIT_LINE/ACTIVE: contracts/v1/contracts.py:448-490; finding_v1 already imports contracts via sys.path insert (scripts/finding_v1.py:18)
- drafts.py, scope.py, contracts.py, findings.py are owned by parallel changes: import only, never edit

## Tasks
1. **Citations: rule_citations, is_spec_gap, CRITERION, struck criteria, spec-gap class** — AC-001 AC-002 AC-003 AC-004 AC-005
   - Files: `scripts/oracle.py`, `scripts/finding_v1.py`, `tests/test_oracle.py`, `tests/test_finding_v1.py`
2. **Scope: no-files exit, text_sha256 drift, commit naming, merges, -z, fences, change-file arrows, warnings** — AC-006 AC-007 AC-008 AC-009 AC-010 AC-011 AC-012 AC-013
   - Files: `scripts/oracle.py`, `tests/test_oracle.py`
3. **Efficiency and reuse: three git calls, markers after the cut, cited_rules and _repo_path gone** — AC-014 AC-015
   - Files: `scripts/oracle.py`, `scripts/finding_v1.py`
4. **Docs** — AC-003 AC-006
   - Files: `commands/hunt.md`, `agents/repro-verifier.md`, `CHANGELOG.md`

## Public Surface
- export `oracle.cited_rules (removed)` — AC-003
- export `oracle.CRITERION (also AC-nnn)` — AC-004

## Test lock
- `tests/test_finding_v1.py` sha256:606201873d2963aef41a86f25812fda5b644e542690d986717f3ee60537454eb
- `tests/test_oracle.py` sha256:3b0fffc31a3727dfb2ed16d772d0496dab8f3c37dec610895b4cc0578290e8d0

## Gate log
- 2026-11-22 Stage 1: pass — plan not stopped for approval: low-risk M
- 2026-11-22 review r1 (run by the coordinator at the end): code FAIL CR-1, no highs; back in Build (already at Stage 2) to fix CR-1 to CR-8 and CR-11 test-first; CR-9, CR-10 tickets
- 2026-11-22 tickets from review r1: CR-9 (every commit message read even when no record names a change), CR-10 (a named merge and its named branch commits counted twice)
- 2026-11-22 review r2 (coordinator): code PASS; low bugs R2-1, R2-2 and cheap R2-7, R2-8 fixed test-first without another round
- 2026-11-22 tickets from review r2: R2-3 (log.showRoot, log.diffMerges, diff.algorithm, GIT_DIR not pinned in _git), R2-4 (all-history numstat cost), R2-5 (brief from the first story file only), R2-6 (check_lock vs check_criteria reading)

## Deviations
- 2026-11-22 tests/test_oracle_followups.py What: a new test file with a second AC-003 test (write --rebuild/--reference on a spec-gap draft citing a criterion) and a docs_dir '.' guard. Why: AC-003's first test didn't reach with_reference's covered= rule; seen failing with the old rule. Effect: AC-003 has two rows.
- 2026-11-22 Task 3 (reuse) What: _repo_path kept instead of scope._relative. Why: _relative resolves absolute paths the hunted repo wrote (follows links) and maps docs_dir '.' to the default. Effect: that reuse ticket stays open, recorded in the change file.
- 2026-11-22 Review What: deferred by the owner's instruction for every parallel lane (relayed by the coordinator); Build commits on the branch after verify, no review, no ship.py, no push. Effect: Stage stays at Build; the coordinator runs reviews at the end.
- 2026-11-22 is_spec_gap What: same signature, now also matches a bold or backticked marker line. Why: AC-002. Effect: drafts.py check and finding_v1, which import it, accept those spellings without being edited.
- 2026-11-22 review r1 fixes What: CR-1 to CR-7 and CR-11 fixed in scripts/oracle.py with tests in a new file tests/test_oracle_review.py (each fix's test seen failing first; the hash-type, CRLF and two citation cases passed before as guards); README.md and commands/hunt.md reworded. Why: code review r1 (FAIL CR-1, no highs). Effect: _git raises BadOracle on a git failure and pins log.showSignature/log.follow; named commits use -m --first-parent; the all-history walk has no pathspec; stories read per criterion file as contracts reads them.
- 2026-11-22 AC-014 What: reworded to count _git calls, not git runs. Why: review r1 CR-8; the test counts _git calls. Effect: AC wording only, same test.
- 2026-11-22 Public Surface What: also STORY_LINE removed from oracle.py, and build() returns a warnings key (printed and dropped by _main). Why: review r1 CR-11. Effect: none for callers in this repo; drafts.py and finding_v1 never used either.
- 2026-11-22 review r2 fixes What: _git runs git with LC_ALL=C and treats a log on a branch with no commits as empty history (no extra call); it reports git's fatal:/error: line and turns an OSError into BadOracle; _numstat resets on a bad header; rule citations need a left boundary before domain.md. The CR-1 failure test now corrupts the HEAD commit object; new tests for an unborn repo, a bad second header and names ending in domain.md, in tests/test_oracle_review.py. Why: code review r2 R2-1, R2-2, R2-7, R2-8. Effect: a repo with staged files and no commits scopes from its state files again.

## Open questions
-
