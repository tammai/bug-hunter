# 2026-11-23-l-audit-stack-coverage
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-23-l-audit-stack-coverage.md   (this feature's record for people)
Track: L   (sized up because: three distinct parts (checklists, OSV-Scanner, Semgrep leads); design settled in brainstorm; footprint: 14 files)
Risk: high   (deploy verdict; third-party tools run on an untrusted target repo; dependency data leaves the machine)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-23
Base: 1c57684
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: 2d58fa6 tree 793d6ff7d63d03d4f4bb55d2a49b5de637a11a6e
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, three parts in order (B1, B2, B3), a verify and a commit after each; reviews once at the end (owner's lane practice)

## Handoff
- checklist selection: scripts/scope.py _checklists (~line 279) and stacks.json security.checklists
- advisory identity: scripts/findings.py _identities and _from_npm_audit (~267) / _from_composer_audit (~312) advisory strings; recheck moves unmatched dependency findings to fixed when the lockfile was audited (~1110-1135)
- audit steps: stacks.json audits, scope.py audits list, commands/audit.md §1 (owner prompt) and §3 step 3 (dependencies)

## Tasks
1. **B1 checklists and OWASP 2025 items** — AC-001 AC-002 AC-003
   - Files: `security/react.md`, `security/typescript.md`, `security/go.md`, `security/rust.md`, `security/python.md`, `security/php.md`, `security/generic.md`, `scripts/stacks.json`, `scripts/scope.py`, `tests/test_audit_stack_coverage.py`
2. **B2 OSV-Scanner for every lockfile** — AC-004 AC-005 AC-006 AC-007 AC-011
   - Files: `scripts/stacks.json`, `scripts/scope.py`, `scripts/findings.py`, `commands/audit.md`, `README.md`, `tests/test_audit_stack_coverage.py`
3. **B3 Semgrep leads** — AC-008 AC-009 AC-010 AC-011
   - Files: `scripts/findings.py`, `scripts/scope.py`, `commands/audit.md`, `agents/security-auditor.md`, `agents/finding-verifier.md`, `README.md`, `tests/test_audit_stack_coverage.py`

## Public Surface
- command `findings.py from-osv-scanner` — AC-005
- command `findings.py from-semgrep` — AC-008

## Test lock
- `tests/test_audit_stack_coverage.py` sha256:41a739261e5b18c3e1b67abb905dd7e9ff0a16b8356b491ab178d7654697d34d

## Gate log
- 2026-11-23 Stage 1: pass — design approved by the owner (L, high risk); dev-only deps excluded where marked
- 2026-11-23 Stage 2: pass

## Deviations
- 2026-11-23 test-change tests/test_audit_stack_coverage.py What: imports sorted (ruff I001). Why: lint. Effect: no assertion changed.
- 2026-11-23 tests/test_audit_scope.py What: the scope helper pins PATH to python's and git's own folders; test_lockfiles_give_dependency_audit_steps expects the npm/composer fallback with its tool key; test_scope_reports_coverage_gaps now expects python, react and go checklists and uses a jvm part for no_checklist. Why: audit steps now depend on whether OSV-Scanner is installed, and those stacks gained checklists by design. Effect: same assertions on the new design; nothing weakened.
- 2026-11-23 security/node.md What: four items added (uploads, exec vs execFile, helmet, outbound URLs) so every stack checklist has at least 15. Why: AC-003. Effect: none on selection.
- 2026-11-23 How the build runs What: B1, B2 and B3 built in one pass with one verify and one commit, not three. Why: they share scope.py, stacks.json and findings.py edits; one verify covered all twelve ACs. Effect: one commit for the build.
- 2026-11-23 security/*.md What: the six new checklists and generic.md's OWASP sections were written by a writer subagent (sonnet) from the owner-approved scope; every CWE in the OWASP sections checked against owasp.json by AC-003. Why: content work in parallel with the code. Effect: none.
- 2026-11-23 README.md What: audit paragraph names the checklists, OSV-Scanner (online/offline, dev-only excluded), the npm/composer fallback and Semgrep leads; gaps list updated. Why: docs restating the changed rules. Effect: docs only.
- 2026-11-23 test-change tests/test_audit_stack_coverage.py What: from-osv-scanner calls pass --exit 1; the go.sum entry's step names go.mod. Why: review round 1 (SEC-06/M4: a failed OSV run prints an empty result, so the conversion needs the exit code; M7: OSV-Scanner rejects go.sum, probed). Effect: no assertion weakened; go.sum stays the audited lockfile.
- 2026-11-23 Semgrep target What: the scope's semgrep step scans . in $RUN/copy and from-semgrep keeps only the parts' files, instead of naming every part's files. Why: review round 1 (SEC-02/H2: target file names on a shell line). Effect: same leads; Semgrep also reads files outside the parts and its own ignore files in the copy.
- 2026-11-23 Design points not built What: dismissed leads are not counted in the report, and an unsettled lead has no path of its own (it reaches Worth a look only as an ordinary suspect that passes check); the overall Semgrep limit is the orchestrator's 10-minute command limit, not a scripted timeout. Why: review round 1 L3; counting needs an auditor output format change, kept out of this change. Effect: report shows no lead counts.
- 2026-11-23 scripts/osv-scanner-empty.toml What: new empty file passed as --config to every OSV run. Why: review round 1 SEC-05, probed: a target osv-scanner.toml with PackageOverrides ignore=true hid all 9 lodash advisories; --config with the empty file restored them. Effect: one new data file.
- 2026-11-23 tests/test_audit_review_fixes.py What: new test file, 13 tests, one per review round 1 finding fixed (lead checks, OSV exit code, severity, dev-optional, fix version, id-less findings, exact ids, escaped errors, scripted Semgrep/offline steps, planted tool, leads_run, audit.md steps). Why: review fixes are test-first; kept apart from the locked AC file. Effect: new tests only.
- 2026-11-23 tests/test_audit_review_fixes.py (round 3) What: the rule-name-word case moved from 'refused' to 'accepted'; added pre-release fix versions, a fixed GHSA advisory moving to fixed beside another, odd OSV shapes, and the planted-tool test drops NoDefaultCurrentDirectoryInExePath from its env. Why: review round 2 M1-r2..M4-r2, L1-r2 (owner chose one more round). Effect: a word a rule is named after no longer triggers the lead check; whole rule ids, the word semgrep and lead spots still do.

## Open questions
-
