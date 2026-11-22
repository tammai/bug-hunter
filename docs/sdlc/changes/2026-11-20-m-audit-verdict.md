# /audit ends with a deploy verdict: Blocked, Not verified or Safe to deploy

## Why

**Request (verbatim):** "hunter need a better security audit, what can we do?"

The owner runs `/audit` by hand before a deploy or go-live, across apps in Node, TypeScript, Vue, React, Go, Rust, Python and PHP. Each app may have a dev environment, UAT, both or neither. What they want from "better" is that the audit is effective: it should find more, and its result should be robust enough to answer "is our code safe to deploy and go live?"

Today the audit can't answer that question. `REPORT.md` is a list of findings. It doesn't say whether anything blocks a deploy. A short report also looks the same whether the code is clean or was barely looked at: parts that `--max` left out, stacks with no checklist of their own, and lockfiles nobody audited only show up as lines under "Coverage". Findings also pile up across runs, so a hole fixed last week still sits in the folder next to new ones.

This is the first of three projects agreed in the brainstorm, in this order:
1. **Verdict and report** (this change).
2. **Stack coverage:** checklists for React, TypeScript, Go, Rust, Python and PHP, OSV-Scanner for every lockfile, and Semgrep hits as leads the auditors must confirm. It also adds checklist items for the OWASP 2025 categories the checklists miss today (A04 and A06–A10), generic and per stack. Approach 1 was chosen there; the owner is asked to install a missing tool when it's needed.
3. **Live `/audit --target`:** proves code findings and probes headers, CORS, rate limits and logout against dev or UAT through the existing proxy, with two or more test users and writes allowed. Never production.

**The user's words:**
- "better means effective, hunt more by robust way to make sure our code safe to deploy and go live"
- Stacks: "nodejs, vuejs, react, typescript, go, rust, python, php"; more popular languages and frameworks later. Environments: "they may be have neither or both dev and uat".
- A clear verdict, the coverage section, and a design that can grow: "add them".
- CI: "skip CI for now".
- Live testing with two or more test users and test-data writes on dev and UAT: "yes sure" (project 3).
- Unconfirmed suspicions: "Show it without blocking".
- A critical or high vulnerable library blocks even when no fix exists: "yes".
- OWASP Top 10: an OWASP tag and per-category coverage table in this change; the checklist gaps (A04, A06–A10, stack-specific items) in project 2: "yes".
- Stack coverage: approach 1, "ask user to install missing tool when need" (project 2).

## Decisions

### Approaches considered (stack coverage, chosen for project 2)

| Approach | Trade-off | Outcome |
|---|---|---|
| 1. Agents + per-stack checklists + OSV-Scanner for all lockfiles + Semgrep hits as leads | Two tools to install. OSV sends the dependency list to osv.dev, as `npm audit` already does with npm. | **Chosen** for project 2. If a tool is missing, the owner is asked to install it; going ahead without it means the verdict is at best Not verified. |
| 2. Agents + each stack's own audit tool (pnpm/yarn audit, govulncheck, pip-audit, cargo audit, composer) | Most precise per language (govulncheck checks reachability), but six tools and six output formats to parse and test. | Ruled out. |
| 3. Agents only, a second auditor pass per part | Nothing to install, but about twice the tokens, and still no dependency audit outside npm and Composer. | Ruled out. |

This change is the base all three projects report through, so it comes first.

### This change

| Decision | Ruled out | Why |
|---|---|---|
| **The verdict is computed by a script.** `findings.py report` computes it from the open findings, the accepted file and `meta.json`, and writes it as the first section of `REPORT.md`. `/audit`'s final message repeats it with its reasons. | The command prompt deciding the verdict | A script can be tested (Principle IV) and gives the same answer for the same inputs. |
| **Three outcomes, worst wins:** **Blocked** > **Not verified** > **Safe to deploy**. | A numeric score, or pass/fail only | The owner needs to know whether they can ship, and "not looked at" must never read as "safe". |
| **Blocked** = at least one open, unaccepted finding that is critical or high. Agent findings count once a verifier has confirmed them. Secret findings count as written by the scan. Critical and high dependency advisories count whether or not a fix is released; one without a known fix is marked "no fix known: replace the package or accept it with a date". | Blocking on medium; blocking only when a fix exists | The owner chose this ("yes"). `composer audit` never reports a fixed version, so a fix-only rule would let a PHP app with a critical advisory read Safe. |
| **Not verified** = nothing blocks, but any coverage gap exists. That covers: a part left out by `--max`; any `paths…` argument (the whole repo wasn't in scope); a folder skipped for an unsafe name; a stack with no checklist of its own (`security/<stack>.md`); a lockfile with no dependency audit, or a failed one; an agent finding that failed `check`; an earlier open finding that couldn't be re-checked. Each gap is listed by name under the verdict. | Treating gaps as notes only | This is what makes "Safe" mean something. Until project 2 lands, every Go, Rust, Python and React repo is Not verified, which is honest. |
| **Safe to deploy** = the whole repo was in scope, there are no gaps, and nothing critical or high is open and unaccepted. Medium and low findings are listed and don't block. | — | — |
| **The verdict names what it covers:** the commit (`git rev-parse HEAD`), whether uncommitted changes were included, the date, and "code only, no live environment" (project 3 adds the environment). | An undated verdict | A deploy of a different commit isn't covered by this verdict, and the owner must be able to see that. |
| **Earlier findings are re-checked, not assumed open.** Every finding in `audit/` that isn't marked fixed is re-checked each run. Scripted findings (secrets, advisories) are re-derived by the scripts: an earlier one this run's scripts don't produce again is marked fixed. Agent findings get one `finding-verifier` each, in a re-check mode: `STILL OPEN` (with the code's current `path:line`), `FIXED — <what changed>`, or `CANNOT CHECK`. CANNOT CHECK keeps the finding open and adds a coverage gap. Fixed findings move to `audit/fixed/NN.md` with the run's date and the reason. The finding's evidence is never rewritten. The re-check cost (about 30k tokens per agent finding) is shown on the cost screen. | Owner marks fixed by hand; counting only this run's findings | The auditors skip known findings, so counting only this run's would report Safe while last week's critical is still in the code. Marking by hand is easy to forget, and stale entries keep blocking. |
| **Line drift isn't "fixed".** In re-check mode the verifier looks for the quoted code itself, not only the cited line. Code that moved but is still there is STILL OPEN, at its new line. | Reusing today's verifier as is | Today a citation that is even one line off is NOT CONFIRMED, so any edit above the code would wrongly mark a finding fixed. |
| **"Worth a look" replaces "Not confirmed (dropped)".** Agent findings the verifier rated NOT CONFIRMED or CANNOT CHECK, and that pass `check`, are kept in `audit/unconfirmed/` (0600). The folder is replaced each run, the files are never numbered, and they are never findings. The report section lists each one: title, first `path:line`, severity as written, and the verifier's verdict line. It never blocks. A suspect that fails `check` is still listed only by file name and the problems found. | Dropping them, as today | The owner chose this, and it needs Principle I amended (below). Replacing the folder each run keeps it to the latest suspicions instead of a growing pile. |
| **Accepted findings** live in `~/.bug-hunter/<host>/<owner>/<repo>/accepted.md`, next to `policy.md`, written by the owner and never by `/audit`. One line per finding: `- 07 until 2026-12-31: <reason>`. An accepted finding doesn't block until its date has passed. After that it blocks again, and the report says "acceptance expired". A malformed line, an unknown number, or a missing or past date is listed in the report as invalid and accepts nothing. The report lists every acceptance in effect. | A permanent "ignore"; keying by title | An expiry date makes the owner look again. Finding numbers never change once assigned, and dedupe keeps them stable across runs. |
| **A removed secret isn't fixed until it's rotated.** A committed secret that a later scan no longer sees stays open, because it's still in git history. The owner closes it with an `accepted.md` line `- 07 rotated: <when, how>`, which needs no expiry date and is allowed only for `secrets` findings. A secret that only ever sat in an uncommitted local file is fixed when it's gone. | Treating it like any other scripted finding | `secrets_scan.py` reads only the current files, so deleting the key would read as Safe while it's still readable in history. |
| **Re-checks follow the run's scope.** Only earlier findings whose root-cause file is in an audited part are re-checked. The rest stay open, untouched, and are listed as a gap ("N earlier findings not re-checked: outside this run's scope"). | Re-checking everything on every run | Principle VI: `--max` and `paths…` must bound the cost. Those runs are Not verified anyway. |
| **Which stacks count as covered.** A gap is any stack or framework detected in scope with no `security/<name>.md`. React is detected from `react` in a `package.json` dependency (the same way Vue is) and needs `security/react.md`. TypeScript is part of `node` and is covered by `node.md`. Files with an `other_extensions` extension (`.sh`, `.cs` …) are a gap: "N files in <ext> with no checklist". Parts made only of config files are covered by `generic`. | Only flagging stacks the owner named | The rule has to be strict to be honest, and it must say *what* is missing so it can be fixed. |
| **A manifest without a lockfile is a gap.** For example `package.json` with no lock, `requirements.txt` or `pyproject.toml` with no lock, or `go.mod` with no `go.sum`. `scope.py` reports the manifest, and the gap names it. | Silently skipping it | Otherwise Safe could mean "dependencies never looked at". |
| **Uncommitted changes are a gap.** If the working tree is dirty, the verdict is at best Not verified ("uncommitted changes: this result matches no commit"). | Only noting it | Auditors and the scan read the working tree, so a dirty Safe describes code that will never be deployed as is. |
| **Finding numbers survive code moving.** Scripted findings are matched to earlier ones by what they are, not where they are: a secret by path plus its fingerprint, an advisory by lockfile, package and advisory id. A STILL OPEN re-check records the code's current `path:line` in a status line appended to the finding, below the untouched evidence, and dedupe also matches on that. An `accepted.md` line therefore keeps working after the code moves. | Keying on the cited line, as `_key` does today | Otherwise an acceptance silently stops applying when a line above the code changes. |
| **OWASP Top 10 (2025) tag and coverage table.** Every finding gets an OWASP category (A01–A10), worked out by `findings.py` from its CWE using a mapping table shipped as data in `scripts/` (a CWE not in the table → `unmapped`). `REPORT.md` gets an OWASP table with one row per category: whether this run's checklists had at least one item for it (an item cites a CWE that maps to the category), and how many findings, by severity, fall under it. A category with no checklist item says "not checked". | Writing the OWASP category into each finding by hand; making OWASP the finding's Category | The owner asked for OWASP coverage. Working it out from the CWE needs no change to the finding format or the agents, and the existing categories stay as they are. |
| **Constitution amendment** (via `sdlc:project-constitution`, 1.2.0 → 1.3.0), Principle I: an agent finding the verifier didn't confirm may be kept as an unconfirmed suspicion, outside the findings, clearly labelled, never numbered, and never counted toward the verdict. Plus a line on the verdict: "Safe to deploy" requires full coverage. | Calling them low-severity findings | Keeps the guarantee that every *finding* survived a disproof attempt. |

**Proposals not asked for:** none beyond the design above. The commit line and the re-check of earlier findings are what make the verdict mean anything (see calls).

### Calls I made (for the owner to check)

1. (Settled by the owner: critical and high advisories block even with no fix known.)
2. **Any `paths…` argument** means Not verified. Safe needs the whole repo in scope.
3. **A stack with no checklist of its own** counts as a coverage gap, so most of your stacks are Not verified until project 2.
4. **Earlier findings are re-checked every run**, at about 30k tokens per open agent finding, shown on the cost screen. Without this, a fixed finding blocks forever or an open one is silently forgotten.
5. `accepted.md` sits **outside the repo**, next to `policy.md` (private, like the findings). Every acceptance needs a date.
6. "Worth a look" shows only **the latest run's** suspicions.
7. A committed secret stays open until the owner writes a `rotated` line. Deleting it isn't enough.
8. Re-checks of earlier findings are limited to this run's scope. Findings outside it are listed as a gap.
9. React gets its own checklist requirement. TypeScript is covered by `node.md`. Files in other languages (`.sh`, `.cs` …) are a gap.
10. A manifest without a lockfile, and uncommitted changes, are both gaps (Not verified).
11. Scripted findings keep their number when their line moves (matched by fingerprint or advisory id).
12. An OWASP category with no checklist item is shown as "not checked" but **isn't a verdict gap**. A06 (insecure design) can never be fully checked, and part 2 fills the other gaps (A04, A07–A10) in the checklists.

### Left to the builder

- The exact `meta.json` keys for the new gaps, and the re-check verdict lines' exact grammar.
- How `findings.py` records "fixed" (the move to `audit/fixed/` plus a note line), as long as numbers are never reused.
- The `/audit` command and `finding-verifier` prompt wording for re-check mode.

## Acceptance criteria

- **AC-001** Given an open, unaccepted critical or high finding (a confirmed agent finding, a secret from the scan, or a dependency advisory with or without a known fix), when the report is written, then `REPORT.md` opens with **Blocked** and names each blocking finding by number. An advisory with no known fix says "no fix known: replace the package or accept it with a date".
- **AC-002** Given nothing blocks but any one coverage gap exists, when the report is written, then the verdict is **Not verified** and the gap is named under it. This holds for each gap on its own:
  - a part left out by `--max`;
  - a `paths…` scope;
  - an unsafe folder;
  - a detected stack or framework (React included) with no `security/<name>.md`;
  - files in `other_extensions`;
  - a lockfile not audited, or an audit that failed;
  - a manifest with no lockfile;
  - uncommitted changes;
  - an agent finding that failed `check`;
  - an earlier finding outside this run's scope, or one re-checked as CANNOT CHECK.
- **AC-003** Given the whole repo is in scope, there are no gaps and no open critical or high finding, when the report is written, then the verdict is **Safe to deploy**, medium and low findings are still listed, and the verdict names the commit, the date and "code only, no live environment".
- **AC-004** Given an `accepted.md`:
  - a valid `- NN until <future date>: <reason>` line stops that finding blocking, and the acceptance is listed in the report;
  - after the date it blocks again, marked "acceptance expired";
  - a malformed line, an unknown number, or a missing or past date is listed as invalid and accepts nothing;
  - none of these cases ends in a traceback.
- **AC-005** Given an earlier advisory, or a secret that only ever sat in an uncommitted local file, that this run's scripts no longer produce, when the run's findings are merged, then it moves to `audit/fixed/NN.md` with the date and reason, and its number is never reused. A **committed** secret the scan no longer sees stays open until `accepted.md` has a `- NN rotated: <note>` line, and `rotated` on a non-secret finding is invalid.
- **AC-006** Given the same secret moved to another line, or the same package and advisory id reported again, when the run's findings are merged, then they keep their earlier number, so an `accepted.md` line still applies.
- **AC-007** Given an earlier agent finding re-checked by a verifier:
  - `STILL OPEN at <path:line>` appends a status line below the untouched evidence, and a later finding at that new line is deduped into it;
  - `FIXED — <what changed>` moves it to `audit/fixed/`;
  - `CANNOT CHECK` keeps it open and adds a gap.
- **AC-008** Given agent suspects the verifier rated NOT CONFIRMED or CANNOT CHECK:
  - those that pass `check` are written unnumbered to `audit/unconfirmed/` (0600), replacing the last run's;
  - they are listed under "Worth a look (unconfirmed, doesn't block)" with title, first `path:line`, severity as written and the verifier's verdict line;
  - they never change the verdict;
  - a suspect that fails `check` is listed only by file name and its problems.
- **AC-009** Given findings with CWEs, when the report is written, then each finding row shows its OWASP 2025 category (A01–A10, or `unmapped`). An OWASP table lists every category, with "checked" or "not checked" taken from the CWEs this run's checklists cite, and the finding counts by severity.
- **AC-010** Given a repo, when `scope.py --focus security` runs, then its JSON names:
  - each part's detected stacks and frameworks that have no checklist, with React detected from `package.json`;
  - files with an `other_extensions` extension;
  - manifests with no lockfile;
  - whether the working tree has uncommitted changes.
- **AC-011** The prompts and docs:
  - `/audit`'s cost screen counts the re-check verifiers;
  - `/audit` re-checks earlier findings in scope, ends by stating the verdict with its reasons;
  - `finding-verifier` has a re-check mode, with the three verdict lines, that looks for the quoted code when lines have moved;
  - the constitution is at 1.3.0, with Principle I allowing unconfirmed suspicions outside the findings;
  - the README documents the verdict, `accepted.md` and "Worth a look".
- **AC-012** Given a secret the scan found, it never appears in a "Worth a look" entry, an `accepted.md` reason echoed in the report, a status line, or a fixed note. Each of these is checked against the fingerprints, as finding lines are today.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_findings.py › test_verdict_blocks_on_open_critical_or_high | `uv run pytest tests/test_findings.py::test_verdict_blocks_on_open_critical_or_high` |
| AC-002 | tests/test_findings.py › test_verdict_is_not_verified_for_each_gap | `uv run pytest tests/test_findings.py::test_verdict_is_not_verified_for_each_gap` |
| AC-003 | tests/test_findings.py › test_verdict_safe_only_with_full_coverage_and_names_the_commit | `uv run pytest tests/test_findings.py::test_verdict_safe_only_with_full_coverage_and_names_the_commit` |
| AC-004 | tests/test_findings.py › test_accepted_findings_expire_and_bad_lines_accept_nothing | `uv run pytest tests/test_findings.py::test_accepted_findings_expire_and_bad_lines_accept_nothing` |
| AC-005 | tests/test_findings.py › test_scripted_findings_fixed_when_gone_but_committed_secrets_need_rotation | `uv run pytest tests/test_findings.py::test_scripted_findings_fixed_when_gone_but_committed_secrets_need_rotation` |
| AC-006 | tests/test_findings.py › test_findings_keep_their_number_when_code_moves | `uv run pytest tests/test_findings.py::test_findings_keep_their_number_when_code_moves` |
| AC-007 | tests/test_findings.py › test_recheck_verdicts_update_earlier_findings | `uv run pytest tests/test_findings.py::test_recheck_verdicts_update_earlier_findings` |
| AC-008 | tests/test_findings.py › test_worth_a_look_lists_unconfirmed_without_blocking | `uv run pytest tests/test_findings.py::test_worth_a_look_lists_unconfirmed_without_blocking` |
| AC-009 | tests/test_findings.py › test_owasp_tags_and_coverage_table | `uv run pytest tests/test_findings.py::test_owasp_tags_and_coverage_table` |
| AC-010 | tests/test_audit_scope.py › test_scope_reports_coverage_gaps | `uv run pytest tests/test_audit_scope.py::test_scope_reports_coverage_gaps` |
| AC-011 | tests/test_plugin_files.py › test_audit_verdict_flow_in_prompts_and_docs | `uv run pytest tests/test_plugin_files.py::test_audit_verdict_flow_in_prompts_and_docs` |
| AC-012 | tests/test_findings.py › test_new_report_sections_withhold_known_secrets | `uv run pytest tests/test_findings.py::test_new_report_sections_withhold_known_secrets` |

## Must never break

- "Safe to deploy" is never written while any gap or any open, unaccepted critical or high finding exists.
- No finding, report line, suspect, status line or fixed note carries a secret the scan saw, even partly.
- A finding's evidence is never rewritten, and a finding number is never reused.
- Audit findings and suspects are never filed or posted (`/hunt-post` still refuses them).
- Every CLI error path ends in one `error:` line, never a traceback.

## Failure modes

- Malformed or hand-edited `accepted.md` (bad dates, unknown numbers, non-UTF-8, CRLF) → AC-004.
- Untrusted text: suspects and agent replies may hold secrets or instructions → AC-012, AC-008 (only checked suspects are kept).
- A crash between writing `fixed/NN.md` and removing `NN.md`: numbering counts both folders, so no number is reused, and a finding found in both is treated as fixed → AC-005.
- `git` unavailable or not a repo when checking for uncommitted changes: treated as a gap ("couldn't tell"), never as clean → AC-002.
- Line drift between runs → AC-006, AC-007.

## Out of scope

- **CI and non-interactive runs:** the owner said "skip CI for now".
- **New stack checklists, OSV-Scanner and Semgrep:** project 2.
- **Live probing of dev or UAT (`/audit --target`):** project 3.
- **Filing or posting findings:** still never (Principle II).
- **A verdict for production environments:** never probed.
- **OWASP checklist content (A04, A06–A10 items):** project 2. This change only tags findings and shows which categories were checked.
- **Asking the owner to install OSV-Scanner or Semgrep:** project 2, when those tools are first used.

## Review

- **Recommended and chosen:** security (`Risk: high`) and code (L, with new public surface), run without asking on the trigger list (L). Each round was a fresh `sdlc:code-reviewer` on opus.
- **Verdicts:** in `.sdlc/.work/findings/2026-11-20-m-audit-verdict/`.
  - Round 1: security FAIL (S1–S5), code FAIL (H1–H3, M1–M5, L1–L2).
  - Round 2: security FAIL (SR2-0) and code FAIL (N1). Both found the same high. The round cap was 2, and the owner chose one more fix round.
  - Round 3: security PASS and code PASS. Their medium and low bugs were fixed test first and closed by `verify.py`.
- **Fixed (highs, each with the test that proves it in `tests/test_findings.py`):**
  - **S1, S3:** names from the target could inject a second `## Verdict` heading or terminal escapes into `REPORT.md`, and a secret in a reason hid the blocking number. `_piece` now escapes control characters and withholds only the secret piece (`test_untrusted_names_cant_forge_the_verdict_or_reach_the_terminal`, `test_a_secret_in_an_expired_reason_never_hides_the_blocking_number`). SR3-0 is the same class in the converters: `_printable` escapes every name a converter writes (`test_scan_names_cant_forge_evidence_lines`).
  - **S2, H2, N1, SR2-0:** facts were frozen at a finding's first sighting.
    - A secret seen uncommitted, then committed, then deleted was marked fixed. Recheck now appends `seen committed`, and `_in_history` asks git before fixing (`test_a_secret_ever_committed_is_never_fixed_by_deleting_it`).
    - Its severity stayed low. `dedupe` now appends `severity now X` and the report ranks on the most severe (`test_a_finding_found_again_at_a_higher_severity_blocks_at_it`).
  - **S4, H3:** a malformed `--scope` gave a traceback or read as clean; it now gets a strict schema check (`test_a_malformed_scope_is_one_error_line`). The id key could recurse forever or be left short; it is now refused unless private, and written whole via temp file and link (`test_the_id_key_is_refused_unless_private_and_never_left_short`).
  - **H1:** findings from before the upgrade got new numbers. Identities are now normalised, with a legacy-key bridge recorded by a status line (`test_findings_from_before_the_upgrade_keep_their_number`).
  - **Medium and low bugs, each with a test:**
    - **S5, SR2-1:** agent findings posing as script output (`check --agent`, `SCAN_MARK`).
    - **M1:** what counts as outside a run's scope.
    - **M2, N6, N7, R3-4, SR2-7:** re-check locations.
    - **M3:** refused suspects and missing verdicts.
    - **M4, N5, R3-1, R3-2, SR3-1:** advisories whose lockfile wasn't audited or is gone.
    - **M5:** the id key's crash window.
    - **L1:** BOM and other list markers in `accepted.md`.
    - **L2–L6:** small report fixes.
    - **N3:** `dirty: 1`.
    - **SR2-2, SR2-3, SR3-2:** `_in_history` uses literal pathspecs, `rev-list`, and no inherited `GIT_DIR`.
    - **SR3-5:** escaped reasons.
- **Tickets** (in `docs/sdlc/todo.md`):
  - R3-3/SR3-3, an acceptance that outlives a severity raise;
  - R3-5/SR3-8, the stale "not committed" title;
  - R3-6 and SR3-4, other facts frozen at first sight;
  - N4, N8 and SR2-9, legacy-key edge cases on the upgrade run;
  - M6, npm `via` order;
  - N9, `--repo` optional;
  - N11, filesystems without hard links;
  - N12, SR2-5 and SR3-2, the pre-existing git calls and inventory cells;
  - S6 and SR3-6, a hostile target's git config;
  - S8, agents editing `accepted.md` during a run;
  - F3, a test to split.
- **Drift and manual checks:**
  - Deviations, all recorded in the state file:
    - Base moved to f72be3d (accepted by the owner at the trust-anchor check).
    - `secrets_scan.py --id-key`, a keyed fingerprint for the approved "path plus fingerprint" identity.
    - `report` reads `--scope` and `--recheck` directly and fails closed.
    - The existing tests moved onto the new shapes.
    - Expired acceptances are listed as "acceptance expired".
    - `commands/audit.md` runs `scope.py` once and sweeps before making the run folder.
    - The extra public surface.
    - Each round's test changes, each re-shown red at the base.
    - An advisory whose lockfile is gone from a clean tree is fixed.
    - The shared `_REPO_VARS`.
  - No AC is `manual`.
  - Superseded by later Decisions: the change file's "Out of scope" doesn't forbid any of these, and this section records where the build departs from Define.
- **Security:**
  - No critical or high finding is open, and the diff holds no secrets.
  - No dependency audit ran: the project has no runtime dependencies (`pyproject.toml` `dependencies = []`), the change adds none, and `pip-audit` isn't installed.
  - The OWASP 2025 CWE lists in `scripts/owasp.json` were read from OWASP's own category pages, not written from memory.
- **Lessons filed:**
  - [knowledge/gotchas/audit-facts-frozen-at-first-sight.md](../../../knowledge/gotchas/audit-facts-frozen-at-first-sight.md);
  - three lines in [recurring-defects.md](../recurring-defects.md).
