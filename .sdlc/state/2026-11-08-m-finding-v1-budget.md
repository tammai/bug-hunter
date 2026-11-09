# 2026-11-08-m-finding-v1-budget
Status: done
Process: 3
Change: docs/sdlc/changes/2026-11-08-m-finding-v1-budget.md   (this feature's record for people)
Track: M   (sized up because: —; footprint: 12 files)
Risk: low
Top model: opus   (fable only if the user chose it)
Commands: test: `uv run pytest`
Started: 2026-11-08
Base: 70d86b1
Owner: tammai.it@gmail.com
Tool: claude-code
Current: Stage 4 – Ship

## Stages
- [x] 1 Define   — the change file, the plan sections below
- [x] 2 Build
- [x] 3 Review   — the change file's ## Review
- [ ] 4 Ship     — PR: (Learn: knowledge, recurring-defects.md)

## How the build runs
inline, one part: spec 04 part 1 is small enough for one session

## Handoff
- Orchestrator answers Q1-Q5 are in the change file's Why; Q1 repro shape is bug-hunter's own until contracts settle cli (deviation from C6)
- scope.py rebuilds out in the --live branch (scripts/scope.py:308): apply --budget after both branches
- contracts.py resolves schemas from its own __file__ (contracts/v1/contracts.py:42), so scripts import it via sys.path
- No pre-release step in knowledge/runbooks/release.md: no -rc tag, no version bump in part 1

## Tasks
1. **Vendor contracts v1 1.1.0 with -text and a drift test; exclude it from ruff** — AC-001
   - Files: `.gitattributes`, `pyproject.toml`, `contracts/v1/`, `tests/test_contracts_vendor.py`
2. **finding_v1.py write: verified draft to C6 file, repro in one function** — AC-002 AC-003
   - Files: `scripts/finding_v1.py`, `tests/test_finding_v1.py`
3. **scope.py --budget at 200k per hunter** — AC-004
   - Files: `scripts/scope.py`, `tests/test_scope.py`
4. **cost_log.py: one validated C7 line per agent run** — AC-005 AC-006
   - Files: `scripts/cost_log.py`, `tests/test_cost_log.py`
5. **C:/Program Files/Git/hunt flags, hunter Severity line, docs** — AC-007
   - Files: `commands/hunt.md`, `agents/bug-hunter.md`, `README.md`, `CHANGELOG.md`

## Public Surface
- command `/hunt --format finding-v1 --out <dir>` — AC-002
- command `/hunt --yes --budget <tokens>` — AC-004
- command `/hunt --cost-log <file>` — AC-005
- command `scope.py --budget` — AC-004
- command `finding_v1.py write` — AC-002
- command `cost_log.py` — AC-005

## Gate log
- 2026-11-08 Stage 1: pass — plan not stopped for approval: low-risk M; orchestrator answered Q1-Q5
- 2026-11-08 state Tasks item 5 title reads 'C:/Program Files/Git/hunt flags' because Git Bash rewrote '/hunt' in the --task argument; it means '/hunt flags'
- 2026-11-08 verify: only the test step fails, 17 failed / 171 passed; the 17 are exactly .sdlc/baseline.md's Windows rows (diffed); AC-001..006 pass; drift covered
- 2026-11-08 review: ran code-review medium (Public Surface not none), not asked: low risk
- 2026-11-08 Stage 2: pass — verify fails only on the 17 baselined Windows tests (see log); ship.py --waive-baseline
- 2026-11-08 round 1 fixes: F1 F2 F3 F5 F6 F7 in scripts/finding_v1.py (tests test_repro_keeps_each_command_with_its_output, test_case_insensitive_names_never_hang, red then green), F8 cost_log tail read, F9 scope simplified; verify fails only on the 17 baselined tests
- 2026-11-08 Stage 2: pass — round 1 fixed; verify fails only on baselined tests
- 2026-11-08 round 2 decision A (orchestrator msg_8f1477a99602): strict finding-v1 step form; finding_v1.py reads only fenced $ blocks at any indent, refuses anything else; heredoc needs its end line; ids capped, a taken name errors; tests red then green; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — round 2 fixed per decision A
- 2026-11-08 round 3 decision A with fallback (orchestrator msg_30b90b5e89df): fixed R3-1 (prompt: unindented fences), R3-2..R3-8 in finding_v1.py, test first; if round 4 finds the step parser wrong again, switch to a hunter-written JSON steps block only after asking
- 2026-11-08 Stage 2: pass — round 3 fixed
- 2026-11-08 Stage 2: pass — JSON repro switch (approved msg_0d63d4bd45f9); verify fails only on baselined tests
- 2026-11-08 round 5 decision A + AC edit accepted (orchestrator msg_5cea66a147cf): whole-line in-order match incl. indentation, exact output lines incl. empty, no command left out, leading '$ ' refused, README one shell + valid JSON, Severity case-insensitive; tests red then green; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — round 5 fixed
- 2026-11-08 round 6 decision D (orchestrator msg_85e5274087c2): JSON repro is the source; render writes Steps; verifier re-runs JSON steps; cross-check deleted; tests red then green; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — decision D built
- 2026-11-08 round 7 decision A (orchestrator msg_671aed769b44; AC edits accepted msg_bd364c546944): verifier runs JSON instead of Steps, markers both sides, installs separate, 600 s timeout, header-only Severity/Set before running on one line, render refuses two Steps, CR-aware fence, $-lines documented; tests red then green; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — round 7 fixed
- 2026-11-08 round 8 decision A (orchestrator msg_56038ebba20d): finding_v1.py runner + prompts; AC-009 red then green; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — round 8 fixed
- 2026-11-08 round 9: user chose ship without runner (msg_a2c194c58850); runner and AC-009 removed; each step alone in its own Bash call; verify fails only on the 17 baselined
- 2026-11-08 Stage 2: pass — runner removed per user decision
- 2026-11-08 round 10 decision A (msg_81439a0b0771): live export + no-copy cd fixed in prompts, Decisions row and Out of scope corrected; verify fails only on the 17 baselined (diffed)
- 2026-11-08 Stage 2: pass — round 10 fixed (prompt text only)
- 2026-11-08 Stage 3: pass — review: r10 fixes applied, round 10 waived as directed; tests fail only on baselined

## Deviations
- 2026-11-08 Task 1 vendored files: contracts/v1/CONTRACTS.md contracts/v1/MANIFEST contracts/v1/acceptance-manifest.schema.json contracts/v1/contracts.py contracts/v1/cost-line.schema.json contracts/v1/criteria-lock.schema.json contracts/v1/departures.schema.json contracts/v1/finding.schema.json contracts/v1/fixtures/bundle/invalid/seed-outside-bundle/http/F-ISS-01.AC2.yaml contracts/v1/fixtures/bundle/invalid/seed-outside-bundle/manifest.json contracts/v1/fixtures/bundle/invalid/seed-outside-bundle/seed/team-eng-11-issues.yaml contracts/v1/fixtures/bundle/invalid/sha256-mismatch/http/F-ISS-01.AC2.yaml contracts/v1/fixtures/bundle/invalid/sha256-mismatch/manifest.json contracts/v1/fixtures/bundle/invalid/sha256-mismatch/seed/team-eng-11-issues.yaml contracts/v1/fixtures/bundle/invalid/url-in-test/http/F-ISS-01.AC2.yaml contracts/v1/fixtures/bundle/invalid/url-in-test/manifest.json contracts/v1/fixtures/bundle/invalid/url-in-test/seed/team-eng-11-issues.yaml contracts/v1/fixtures/bundle/valid/trackr/http/F-ISS-01.AC2.yaml contracts/v1/fixtures/bundle/valid/trackr/manifest.json contracts/v1/fixtures/bundle/valid/trackr/seed/team-eng-11-issues.yaml contracts/v1/fixtures/cost/invalid/negative-wall-s.jsonl contracts/v1/fixtures/cost/valid/cost.jsonl contracts/v1/fixtures/criteria/invalid/grammar.md contracts/v1/fixtures/criteria/invalid/no-example-data.md contracts/v1/fixtures/criteria/invalid/no-source-tag.md contracts/v1/fixtures/criteria/invalid/sdlc-m--standalone-id-with-reverse-tag.md contracts/v1/fixtures/criteria/valid/sdlc-m--no-example-data-is-a-warning.md contracts/v1/fixtures/criteria/valid/spec-example.md contracts/v1/fixtures/departures/invalid/no-decided-by.yaml contracts/v1/fixtures/departures/invalid/proposed-blocks.yaml contracts/v1/fixtures/departures/valid/departures.yaml contracts/v1/fixtures/finding/invalid/borrowed-question-shape.json contracts/v1/fixtures/finding/invalid/no-verified-by.json contracts/v1/fixtures/finding/invalid/route-mismatch.json contracts/v1/fixtures/finding/valid/BH-0007.json contracts/v1/fixtures/finding/valid/BH-0008-not-reproduced.json contracts/v1/fixtures/finding/valid/SQ-0001-spec-question.json contracts/v1/fixtures/http/invalid/capture-used-before-taken.yaml contracts/v1/fixtures/http/invalid/json-not-a-list.yaml contracts/v1/fixtures/http/invalid/no-steps.yaml contracts/v1/fixtures/http/valid/F-ISS-01.AC2.yaml contracts/v1/fixtures/lock/invalid/level-2-without-test.json contracts/v1/fixtures/lock/invalid/tag-with-brackets.json contracts/v1/fixtures/lock/valid/trackr/criteria.lock.json contracts/v1/fixtures/lock/valid/trackr/docs/specs/trackr/features/F-ISS-01-create-issue.md contracts/v1/fixtures/story/invalid/edge-cases-section.md contracts/v1/fixtures/story/invalid/failure-mode-without-arrow.md contracts/v1/fixtures/story/valid/F-ISS-01-create-issue.md contracts/v1/fixtures/yaml/invalid/anchor.yaml contracts/v1/fixtures/yaml/invalid/block-scalar.yaml contracts/v1/fixtures/yaml/invalid/duplicate-key.yaml contracts/v1/fixtures/yaml/invalid/empty-key.yaml contracts/v1/fixtures/yaml/invalid/unclosed-flow-value.yaml contracts/v1/fixtures/yaml/valid/scalars.yaml contracts/v1/test_contracts.py and their exports BadDraft SchemaUnsupported YamlError check_bundle check_cost check_criteria check_departures check_finding check_http_test check_id check_lock check_story criterion_text_sha256 finding_route header_for main parse_yaml run_fixtures run_http schema_errors seal sum_cost vendor_check. What: the plan named the folder contracts/v1/, drift checks each file and each export. Why: CONTRACTS.md requires the whole folder byte-identical, never edited. Effect: none; the files are exactly the MANIFEST at sha256 4064651b.
- 2026-11-08 scripts/finding_v1.py exports BadDraft finding repro_from_draft write; scripts/cost_log.py exports line. What: module-level functions the scripts' CLIs use, not listed in Public Surface. Why: the surface lists the CLIs, which are the interface. Effect: none.
- 2026-11-08 C6 repro What: repro is bug-hunter's own cli shape {runner: cli, steps: [{command, stdout}], env} rather than a C4 runner format. Why: contracts v1 leaves cli unsettled; the user chose (a) via the orchestrator. Effect: contracts.py does not check it; documented in README; HTTP replay comes in part 3.
- 2026-11-08 AC-002 AC-003 and Decisions in the change file What: the repro now comes from a hunter-written '## Repro (finding-v1)' JSON list checked in order against the visible Steps, not from parsing Steps markdown. Why: review rounds 1-4 kept finding mis-parses (round 4: heredoc body split into made-up steps); orchestrator approved the switch (msg_0d63d4bd45f9). Effect: markdown step parser and heredoc rules deleted; hunter prompt and /hunt describe the section; default mode unchanged.
- 2026-11-08 AC-002 AC-003 AC-008 Decisions and agents/repro-verifier.md What: decision D, the Repro JSON is the source; render writes Steps from it, the verifier re-runs the JSON steps, write uses it; AC-008 added for render; AC-004 text corrected to the test's 5 parts / left_out 3. Why: rounds 5-6 showed cross-checking JSON against hand-written Steps keeps breaking; orchestrator decided D and accepted the AC edit (msg_85e5274087c2). Effect: no matching code; repro-verifier.md gains a finding-v1 paragraph (default unchanged).
- 2026-11-08 scripts/finding_v1.py export repro_steps and render What: functions behind the render/write CLIs; AC-008's red was seen before its code (invalid choice 'render') and recorded afterwards by hiding the render subcommand for one run. Why: decision D added render after the red step. Effect: none on behaviour.
- 2026-11-08 AC-009 and scripts/finding_v1.py runner What: new runner subcommand writes steps.sh (one brace group per JSON step, output to out/<n> with 2>&1); hunter and verifier prompts use it instead of one hand-split Bash call. Why: review round 8 (installs run twice, truncation, glued markers); orchestrator decision A (msg_56038ebba20d). Effect: AC-009 added with its test, red recorded before the code.
- 2026-11-08 AC-009 removed, runner removed from scripts/finding_v1.py What: user decision (msg_a2c194c58850) to ship without the one-shell runner; each JSON step runs alone in its own Bash call from the copy's root, wrapped as { cmd } 2>&1. Why: review round 9 found highs in the runner (background jobs not reaped, stale out files, relative --dir). Effect: shared shell state between steps is a known limit and ticket; prompts and README say steps stand alone.
- 2026-11-08 waived round 10: R10-2 R10-3 — fixed in prompt text (agents/bug-hunter.md, agents/repro-verifier.md) as listed in decision A, then committed without a further review round, as the orchestrator directed (msg_81439a0b0771). What: no round-11 re-check of two prompt edits. Why: orchestrator/user decision to fix and ship locally. Effect: the fixes are unreviewed prompt text.

## Open questions
-
