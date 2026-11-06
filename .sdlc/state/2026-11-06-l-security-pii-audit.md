# 2026-11-06-l-security-pii-audit
Status: active
Process: 3
Change: docs/sdlc/changes/2026-11-06-l-security-pii-audit.md   (this feature's record for people)
Track: L   (sized up because: approach unclear at start; new agent type, finding format, report, constitution and PRD change; footprint: 22 files)
Risk: high   (security tooling: secrets handling, PII, agents running target code; amends the constitution)
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-06
Base: e3cc6e3
Owner: tam.mai@bigin.vn
Tool: claude-code
Verified: dc50a77 tree 48fcd598c16c1f8101a20c546adb135ce4edafd2
Slice: B4   Slice base: dc9f54e   Slice gates: none
Current: Stage 3 – Review

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [ ] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, in parts (backlog): four parts too large for one session's context

## Handoff
- Constitution I conflicts with traced findings: amend via sdlc:project-constitution in B4, once the owner approves
- Reuse scope.py _safe_folder/_installs rules for audits (scripts/scope.py); drafts.numbered/next for numbering (scripts/drafts.py)
- Secret guardrail patterns: .claude/hookify/sdlc-secret-values.md line 9; keep scripts/secret_patterns.json in sync by test

## Tasks
1. **B1 scope --focus security, checklists, audits** — AC-001 AC-002
   - Files: `scripts/scope.py`, `scripts/stacks.json`, `tests/test_audit_scope.py`
2. **B2 secrets scan** — AC-003
   - Files: `scripts/secrets_scan.py`, `scripts/secret_patterns.json`, `tests/test_secrets_scan.py`
3. **B3 findings.py and guards** — AC-004 AC-005 AC-006 AC-007 AC-008
   - Files: `scripts/findings.py`, `scripts/post.py`, `scripts/known.py`, `tests/test_findings.py`
4. **B4 agents, checklists, /audit, constitution, PRD, README** — AC-009 AC-010 AC-011 AC-012
   - Files: `agents/security-auditor.md`, `agents/finding-verifier.md`, `security/generic.md`, `security/node.md`, `security/vue.md`, `security/pii.md`, `commands/audit.md`, `docs/sdlc/constitution.md`, `docs/sdlc/prd.md`, `README.md`, `tests/test_plugin_files.py`, `knowledge/index.md`

## Public Surface
- command /audit [paths] [--max N] — AC-011
- scripts/scope.py --focus security; JSON parts[].checklists, audits — AC-001 AC-002
- scripts/secrets_scan.py <repo> — AC-003
- scripts/findings.py check|dir|next|from-secrets-scan|from-npm-audit|from-composer-audit|inventory|report — AC-004..AC-007
- scripts/known.py --audit — AC-008
- agents security-auditor, finding-verifier — AC-009
- owner file ~/.bug-hunter/<host>/<owner>/<repo>/policy.md (optional) — AC-009 AC-011

## Gate log
- 2026-11-06 Stage 1: pass — change file approved by the user: amend constitution I for traced findings; report-only; optional owner policy.md
- 2026-11-06 Stage 2: pass
- 2026-11-06 review: ran security, code high (Risk: high; L; Public Surface), self-chosen: L
- 2026-11-06 Stage 3: fail — review r1: security S1, S2 (+S3-S6); code H1-H4, M1-M4 (+L1-L4, F1); all fixed now
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r2: security N1, S2, N3 (+T1-T3); code N1-N3 (+T1); user: fix until no findings
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r3: security R3-1..R3-4, code N4; user chose round 4 with the known-values design
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r4: security R4-1..R4-3 (+R4-4, R4-6); code H5, M5 (+L1-L5); user chose round 5
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r5: security R5-1..R5-3, code N1 (+T6, T8, T9, load_prints); user chose round 6
- 2026-11-06 Stage 2: pass
- 2026-11-06 Stage 3: fail — review r6: security R6-1; code B1, B2 (+T12); user chose round 7
- 2026-11-06 Stage 2: pass

## Deviations
- 2026-11-06 scripts/scope.py What: the unsafe-folder warning now prints once per folder after both installs and audits, reading 'no install or audit for …'. Why: audits reuse the install rules, so the same folder warned twice. Effect: the existing count of 6 warnings in test_stacks still holds.
- 2026-11-06 .claude/rules/plugin-prompts.md What: rule updated to match constitution 1.1.0 (audit proof levels, audit findings never posted, <redacted>) and now loads for security/**. Why: the constitution skill flagged it as contradicting the amended Principle I. Effect: prompt-editing sessions get the right rule.
- 2026-11-06 commands/audit.md What: the secrets scan reads the repo itself, not the throwaway copy. Why: the copy (a clone) lacks local untracked .env files, which the scan must cover; the scan only reads. Effect: differs from the change file's flow step 3-4 wording (review F1).
- 2026-11-06 commands/audit.md, tests/test_plugin_files.py What: findings are screened with findings.py check before verifiers see them, and deduped with the new findings.py dedupe against earlier runs. Why: review S3 (an unscreened finding could carry a secret into a verifier prompt) and M4 (re-runs refiled scripted findings). Effect: AC-011's step-order test now has check before the verifier and dedupe before next.
- 2026-11-06 scripts/findings.py, scripts/secrets_scan.py, scripts/scope.py, scripts/stacks.json, tests/* What: review round 1 fixes: whole-value placeholder rule shared by scan and check; strict NAME=value env pattern in check; every REPORT.md and inventory line scrubbed; npm error JSON and missing results are failures; npm fix names the package to upgrade; meta validated; inventory skips the header, accepts outer pipes and merges earlier runs; fsync; per-line most-severe hit; $-prefixed values reported unless references; unreadable files skipped; AWS/private-key patterns case-sensitive; ignored dirs listed with --directory; lockfiles out of --focus security; composer audit --no-plugins --no-scripts. Why: review S1, S2, S4, S5, S6, H1-H4, M1-M3, L1-L4. Effect: the test that {} is a clean npm audit now expects a failure; AC-002's composer command changed.
- 2026-11-06 scripts/secrets_scan.py What: is_placeholder is a module function imported by findings.py. Why: the scanner and findings.py check must apply the same whole-value placeholder rule (review S2/S4). Effect: one definition of what counts as a placeholder.
- 2026-11-06 scripts/secrets_scan.py, scripts/secret_patterns.json, scripts/findings.py, tests/* What: round 3. is_placeholder counts only whole placeholders (<...> or an unclosed <word, ${...}, exact words, a key prefix then x's); new masked-key pattern (known prefix, real characters, then masking); findings/report check catches NAME=value anywhere on a line, spaced or quoted, unless the value is code, plus long base64 key bodies; scanner adds a glob query for .env files inside ignored folders; dedupe keys on the root-cause path:line (fix-here case-insensitive), merges dropped duplicates' Where lines, refuses the same folder twice. Why: review r2 security N1, S2, N3, T1, T2; code N1, N2, N3, T1. Effect: placeholder word list is now exact-match only; T3 ($pw read as a .env variable reference) stays, by dotenv convention.
- 2026-11-06 scripts/secrets_scan.py, scripts/secret_patterns.json, scripts/findings.py, commands/audit.md, README.md, tests/* What: round 4, the user-approved known-values design. secrets_scan.py --fingerprints writes SHA-256 hashes of every found secret and of its 8-character slices (single-case-alpha slices left out) to scratch; findings.py check/inventory/report take --fingerprints and withhold any line holding a known secret or slice; the free-text NAME=value and base64-body guesses are removed; new jwt, masked-key (any mask, left boundary) and hardcoded-credential (quoted, letters+digits) patterns; is_placeholder accepts masking alone or after a known key prefix, placeholder words with letter-only suffixes, all-*; _merge_where finds the heading by line; the ignored-.env glob excludes skip_dirs. Why: review r3 security R3-1..R3-4 and code N4, T2-T6: shape-guessing kept trading leaks for rejected findings. Effect: AC-004's partial-redaction cases moved to the fingerprint test; a secret the scan never saw and with no known shape is guarded only by the agents' <redacted> rule (README says so).
- 2026-11-06 scripts/secrets_scan.py What: counts, windows, fingerprints and known_secret_in are module functions; findings.py imports counts and known_secret_in. Why: the scanner writes fingerprints and findings.py checks text against them with the same slicing rule, so it lives in one place. Effect: no new CLI surface beyond --fingerprints.
- 2026-11-06 scripts/secrets_scan.py, scripts/secret_patterns.json, scripts/findings.py, commands/audit.md, README.md, tests/* What: round 5. Fingerprints store value lengths and every known value is searched at every position (not split tokens); 12-character single-case slices fingerprinted; private-key body lines fingerprinted and KEY_BODY (mixed-case base64 line) restored; trivial values (digits, booleans, under 4) not reported, and short or word-like values not fingerprinted; ... and … count as masking; masked-key adds <redacted>, [redacted], (truncated); new key-fragment pattern (known prefix plus 4+ chars with a digit); hardcoded-credential values exclude : and /; fingerprints loaded once as sets and shape-checked; Where merge finds headings like _parse; the ignored-.env glob skips build and venv folders; /audit cleans scratch on early stop and calls the fingerprints sensitive. Why: review r4 security R4-1..R4-4, R4-6; code H5, M5, L1-L5. Effect: load_prints is a new shared helper.
- 2026-11-06 scripts/secrets_scan.py, scripts/secret_patterns.json, commands/audit.md, tests/* What: round 6. Key bodies: a one-line key's base64 runs (after turning literal \n into newlines) are fingerprinted; END on the header line closes it; only base64 lines continue a body, anything else ends it and is scanned normally; hardcoded-credential allows / and : again but skips URLs, leading-/ paths and :lowercase namespaces; URLs, paths and any letters-only word value under 12 letters aren't fingerprinted; sk-ant-api03-style docs prefixes count as placeholders; load_prints requires lengths/values/windows/long_windows lists; /audit's scratch-cleanup rule moved to right after scratch is made. Why: review r5 security R5-1..R5-3, T6, T8; code N1, T8, T9. Effect: weak letters-only passwords under 12 letters stay an accepted residual (reported by the scan, not fingerprinted).
- 2026-11-06 scripts/secrets_scan.py, tests/test_findings.py What: round 7. A leading / counts as a path only for lowercase path segments (and lowercase relative file paths like certs/server1.pem); key-body lines are recognised bare or quoted and joined in code ("...\\n" +); legacy Proc-Type/DEK-Info lines and the blank line don't end a body; a one-line key's capture stops at END. Why: review r6 security R6-1 (base64 starting with / was treated as a path), code B1, B2, T12. Effect: none beyond the fixes.

## Open questions
-
