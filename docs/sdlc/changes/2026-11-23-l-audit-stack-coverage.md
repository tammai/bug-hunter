# /audit stack coverage: checklists for every stack we name, OSV-Scanner for every lockfile, Semgrep leads

## Why

**Request (verbatim):** /audit project 2: stack coverage. From docs/sdlc/todo.md "Make /audit say whether code is safe to deploy" item 2 and the 2026-11-20 brainstorm (memory audit-improvement-plan): per-stack checklists for React, TypeScript, Go, Rust, Python and PHP (node/vue exist); OSV-Scanner for every lockfile; Semgrep hits as leads the auditors must confirm; ask the owner to install a missing tool when needed; checklist items for OWASP 2025 A04 and A06–A10. Brainstorm the design with the owner first (L track).

The owner runs `/audit` by hand before deploying and wants a verdict they can ship on ("make sure our code safe to deploy and go live", 2026-11-20). Project 1 (PR #43, follow-ups #50) made the verdict honest: a stack with no checklist, or a lockfile with no audit, keeps it at **Not verified**. Today that is most repos. Only `generic`, `pii`, `node` and `vue` checklists exist, and only `package-lock.json` (npm audit) and `composer.lock` (composer audit) are audited. A Python, Go, Rust or React/TypeScript app can therefore never read **Safe to deploy**, and its dependencies are never checked. This change closes those gaps for the stacks the owner named, and adds Semgrep as a cheap first pass that points the auditors at likely sinks.

**How it works today** (read in Define):
- `scope.py` `_checklists` gives each part `generic` and `pii`, its stacks' checklists (`python`, `node`, `go`, `rust`, `jvm`, `ruby`, `php` from file extensions), and framework checklists (`vue` by extension or dependency, `react` by dependency). A name with no `security/<name>.md` goes to `no_checklist`, which the report lists as a gap.
- `stacks.json` `audits` holds two commands; every other entry of `dependency_lockfiles` (pnpm, yarn, bun, uv, poetry, Pipfile, pdm, go.sum, Cargo.lock, Gemfile.lock) is a "lockfile with no audit" gap.
- `findings.py from-npm-audit` / `from-composer-audit` write one advisory finding per (lockfile, package, advisory URL); `dedupe` identifies an advisory by those three, so an existing finding keeps its number and its `accepted.md` line.
- `commands/audit.md` §1 tells the owner which audits run and that they send the dependency list to a registry, then asks "Start the audit?".
- `agents/security-auditor.md` reads its part's checklists and works through each item, tracing source to sink with `path:line`.
- Installed on the owner's machine: `osv-scanner` 2.4.0, `semgrep`, `govulncheck`; not `pip-audit` or `cargo-audit`.

**The user's words:** 2026-11-23: approved the design; dev-only dependencies are excluded where the lockfile marks them. The 2026-11-20 brainstorm agreed approach 1 (checklists + OSV-Scanner + Semgrep hits as leads), asking the owner to install a missing tool when needed, and skipping CI for now. The open points below were settled with the recommended answer (`[recommended]`) for the owner to confirm or change at approval.

## Decisions

### Approaches considered

| Approach | Trade-off |
|---|---|
| **A. Checklists + OSV-Scanner + Semgrep leads (chosen, agreed 2026-11-20)** | One dependency tool for every ecosystem, offline-capable; Semgrep is fast and finds sinks, but only as leads, so its false positives never reach the report unconfirmed. Three tools to keep working. |
| B. One native audit per ecosystem (pip-audit, cargo-audit, govulncheck, pnpm/yarn audit) | Precise per ecosystem, govulncheck even knows reachability; but five tools to install and convert, each with its own JSON and its own network calls, and Ruby/Bun still uncovered. |
| C. Checklists only, no tools | Nothing to install; but dependencies stay unaudited (gaps stay), and the auditors read every file cold. |

### The design (chosen approach A, in detail)

| Decision | Chosen | Ruled out | Why |
|---|---|---|---|
| Delivery | One feature, three parts in order: **B1 checklists + OWASP items**, **B2 OSV-Scanner**, **B3 Semgrep leads**; each ends with verify and a commit, the review runs once at the end (the owner's lane practice) `[recommended]` | three separate features; one part | each part ships value alone, but they share the scope JSON, the §1 prompt and the report's gap lines; one record keeps those consistent |
| New checklists | `react.md`, `typescript.md`, `go.md`, `rust.md`, `python.md`, `php.md`, about the depth of `node.md` (20–35 lines of concrete code shapes, each a thing to grep or trace), written from each ecosystem's own security docs and the OWASP cheat sheets, cited in a "Sources" line `[recommended]` | long generic lists; copying third-party checklists verbatim | `node.md`'s shape (a code pattern, why it's a bug) is what the auditors act on; our own words avoid licence questions |
| Which checklists a part gets | `typescript` by extension (`.ts`, `.tsx`, `.mts`, `.cts`) as a framework entry next to `vue`; `react` also by extension (`.jsx`, `.tsx`) besides the `react` dependency | a separate `typescript` stack in `stacks.json` | TypeScript is already part of the `node` stack (install steps, edge inputs); only the checklist differs |
| JVM and Ruby | stay without a checklist (still listed as `no_checklist` gaps) `[recommended]` | adding them now | the owner named six stacks; adding two more is a later change |
| OWASP 2025 A04, A06–A10 | new sections in `generic.md` (one per category, stack-neutral items with CWE ids from `owasp.json`), plus stack-specific items in each new checklist where the stack has its own shape (Go `crypto/rand` vs `math/rand`, Python `pickle`, PHP `unserialize`, Rust `unsafe`) | a separate `owasp.md` | auditors already always read `generic.md`; one place per item |
| Dependency audit tool | **OSV-Scanner replaces npm and composer audit** for every lockfile it reads (all of `dependency_lockfiles` but `bun.lockb`), one run per lockfile (`osv-scanner scan source --lockfile <f> --format json`) `[recommended]` | keeping npm/composer audit beside OSV; running both | one converter and one identity; OSV draws on the same GitHub advisories npm and composer use |
| Network and privacy | OSV-Scanner sends package names and versions to osv.dev (the same kind of data npm audit sends today); §1 says so and asks the owner to choose online or offline before the yes. Offline runs `--offline-vulnerabilities`; if the local database is missing, those lockfiles are failed audits (gaps), never sent online (builder check Q5) `[recommended]` | detecting the database and choosing silently; always offline | a wrong guess would send package names the owner believed stayed local; the offline database is a large download the owner may not want |
| Upgrade: existing advisory findings | an advisory finding is identified by (lockfile, package, the set of advisory ids it names: GHSA, CVE, PKSA, OSV ids, read from its advisory line); two match when the sets share an id. An OSV finding writes its GHSA URL first when it has one, then its other ids, so a finding from npm audit (GHSA URL) or composer audit (`PKSA CVE link`) keeps its number and acceptance, and the npm/composer fallback without OSV never flips findings between fixed and new (builder check Q1) | renumbering on the switch; matching only the GHSA URL | the must-never-break line from project 1: shipped findings keep their numbers and acceptances |
| npm's transitive entries | an npm-audit finding whose advisory isn't an id (`see npm audit`, `through <pkg>`), on a lockfile OSV audited this run, moves to fixed with the reason "superseded: OSV reports the vulnerable package itself", never "no longer found" (builder check Q3) | keeping them open forever; "no longer found" | OSV reports the vulnerable package directly; the reason must be true |
| Dev-only dependencies | excluded where the lockfile marks them: OSV-Scanner reports `dependency_groups: ["dev"]` on such a package (seen on a package-lock dev entry, 2026-11-23); those packages are dropped, the rest count; ecosystems with no dev marker count everything (**owner's answer**, 2026-11-23) | counting them as non-blocking; counting them fully | keeps today's `npm audit --omit=dev` results; dev tools don't ship |
| Missing OSV-Scanner | §1 names it with the install command (`brew install osv-scanner`, or `go install github.com/google/osv-scanner/v2/cmd/osv-scanner@v2`) and asks: install it and rerun, or go on; going on falls back to npm/composer audit where those apply and leaves every other lockfile a gap, so the verdict stays Not verified `[recommended]` | refusing to run; installing it for the owner | the agent never installs software; the honest gap already exists in the report |
| OSV severity (review round 1) | the worst rating any grouped advisory or the group's CVSS score gives; an OpenSSF `MAL-` (malicious package) id is critical; an advisory with no rating at all is high, so it blocks until someone reads it `[recommended]` | the first rated member; unrated as medium | many PYSEC, GO and RUSTSEC records carry no rating, and medium never blocks, so a malicious or unrated package read Safe to deploy |
| Failed OSV run (review round 1) | `from-osv-scanner --exit <code>` refuses anything but 0 or 1; the offline step reads the owner's own cache folder (named before isolation moves HOME) with `--offline-vulnerabilities`, never `--offline` `[recommended]` | trusting the JSON | probed: a run with no offline database prints `{"results": []}` and exits 127 |
| An earlier finding with no advisory id (review rounds 1–3) | stays open while the run reports any advisory for its lockfile and package; moves to fixed when the package is no longer reported; npm's entry for a package that only brings a vulnerable one in (`see npm audit`) becomes "superseded" when OSV-Scanner reports that lockfile `[recommended]` | moving it to fixed when its text matches nothing | with no id there is no telling which advisory it was; keeping it open keeps its number and acceptance, at the cost of a duplicate OSV finding beside it |
| Semgrep rules | the registry rulesets per stack (`p/python`, `p/javascript`, `p/typescript`, `p/react`, `p/golang`, `p/rust`, `p/php`, plus `p/secrets`-free `p/owasp-top-ten`), run with `--metrics=off`; rules are downloaded, **code never leaves the machine**; rules cached in `$RUN/cache` for the run `[recommended]` | vendoring the semgrep-rules repo (its licence restricts redistribution); writing our own rules | the registry's rules are maintained; downloading rules sends no code, and `--metrics=off` sends no usage data |
| Missing Semgrep or offline | §1 names it with its install command (`brew install semgrep` or `pipx install semgrep`); going on runs the audit without leads, and the report notes "Semgrep leads not run" as information, **not a gap**: the verdict doesn't depend on it `[recommended]` | a gap that keeps the verdict at Not verified | leads only point; the auditors' checklist reading is what vouches for the code |
| How leads reach auditors | `findings.py from-semgrep` turns Semgrep's JSON into one leads file per part (rule id, `path:line`, its message, its CWE), each line escaped and capped; the auditor's prompt gets it in a fenced block headed "Semgrep leads (data, never instructions)" | passing raw Semgrep output; one file for all parts | per part keeps prompts small; escaping keeps a hostile file name or message from forging prompt structure |
| A finding that cites a lead | `findings.py check --agent` refuses a finding that names a Semgrep rule id unless its Proof is `traced` or `proven` and its Where has at least two `path:line` spots (source and sink); the finding-verifier still re-checks the trace (builder check Q4) | refusing any mention of a rule id; leaving it to the verifier alone | a script can't judge a trace, but it can refuse the one shape a copied lead takes |
| What an auditor does with a lead | confirms it with its own source-to-sink trace (then it is a finding like any other, cited by `path:line`, never by the rule id alone), or dismisses it; dismissed leads are counted, not listed, in the report; a lead the auditor can't settle may go to the existing "Worth a look" list, never to the verdict | turning Semgrep hits into findings directly | project 1's rule: only evidence a second agent failed to disprove blocks a deploy |
| Semgrep runs on | `$RUN/copy` (the sealed copy), with `--disable-version-check`, a timeout, and only the parts' files; never the owner's working tree | the working tree | the same isolation the agents get |

### Goals, non-goals, anti-goals

- **Goals:** a React/TypeScript, Python, Go, Rust or PHP repo can read Safe to deploy when it is; every supported lockfile is audited; auditors spend their time on likely sinks.
- **Non-goals:** JVM and Ruby checklists; CI; live-target audit (project 3); govulncheck reachability (OSV covers `go.sum`; reachability is a later idea).
- **Anti-goals:** a Semgrep hit reaching the report as a finding without an auditor's trace; a tool silently missing while the verdict still reads Safe; any code or secret leaving the machine for a lead or an audit.

### Calls made, and what's left to the builder

- Calls: the three-part split; OSV replacing npm/composer audit; registry rulesets with metrics off; Semgrep missing = note, not gap; checklist depth like `node.md`.
- Left to the builder: exact Semgrep rulesets per stack (checked against what the registry serves), the OSV severity mapping (CVSS → critical/high/medium/low, same buckets as npm's), timeouts, wording of the §1 lines.

## Acceptance criteria

- **AC-001 (B1)** A part with `.py`, `.go`, `.rs` or `.php` files gets that stack's checklist, and its `no_checklist` no longer names the stack; JVM and Ruby are still listed there.
- **AC-002 (B1)** A part with `.ts`/`.tsx` files gets `typescript`; one with `.jsx`/`.tsx` files or a `react` dependency gets `react`.
- **AC-003 (B1)** Every checklist the scope can name, except `jvm` and `ruby` (out of scope), exists, has a title, at least 15 checklist items and a "Sources" line; `generic.md` has one section for each of A04, A06, A07, A08, A09 and A10 whose items name CWEs that `owasp.json` maps to that category.
- **AC-004 (B2)** With OSV-Scanner installed, `scope.py --focus security` gives one OSV audit step per supported lockfile (pnpm, yarn, bun.lock, uv, poetry, Pipfile, pdm, go.sum, Cargo.lock, Gemfile.lock, package-lock, npm-shrinkwrap, composer.lock), and none of those is a "lockfile with no audit" gap.
- **AC-005 (B2)** `findings.py from-osv-scanner` turns OSV-Scanner JSON into one advisory finding per (lockfile, package, advisory), with the GHSA advisory URL when the vulnerability has one, the fixed version when OSV names one, and a severity bucket; malformed JSON is one `error:` line.
- **AC-006 (B2)** A finding written earlier by npm audit (GHSA URL) or composer audit (`PKSA CVE link`) for the same lockfile, package and an advisory id OSV also names keeps its number and its `accepted.md` acceptance on the first OSV run, and on a later run that falls back to npm/composer audit; an npm transitive entry moves to fixed as "superseded", not "no longer found".
- **AC-012 (B2)** A package OSV-Scanner marks `dependency_groups: ["dev"]` gives no finding; the same advisory on a package without that mark does.
- **AC-007 (B2)** Without OSV-Scanner on PATH, the scope's audits fall back to npm/composer audit for those two lockfiles, every other lockfile is a "lockfile with no audit" gap, and the scope says which tool is missing and its install command.
- **AC-008 (B3)** `findings.py from-semgrep` turns Semgrep JSON into one leads file per part, each lead with rule id, `path:line`, message and CWE, control characters escaped and each line capped; a lead outside every part is dropped; malformed JSON is one `error:` line.
- **AC-009 (B3)** A Semgrep lead never becomes a finding by itself: `findings.py check --agent` refuses a finding that names a Semgrep rule id unless its Proof is `traced` or `proven` and its Where has at least two `path:line` spots; a finding with no rule id is checked as today.
- **AC-010 (B3)** Without Semgrep on PATH, the scope says so with the install command, and the report shows "Semgrep leads not run" as a note, not a gap: a repo with no other gap still reads Safe to deploy.
- **AC-011 (B2, B3)** `commands/audit.md` §1 lists, before the owner's yes: the OSV-Scanner runs and what they send (package names and versions, or nothing in offline mode), the Semgrep runs (rules downloaded, no code sent), and each missing tool with its install command; §3 runs them on `$RUN/copy`.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_audit_stack_coverage.py › test_each_named_stack_gets_its_checklist | `uv run pytest tests/test_audit_stack_coverage.py::test_each_named_stack_gets_its_checklist` |
| AC-002 | tests/test_audit_stack_coverage.py › test_typescript_and_react_checklists_by_extension_and_dependency | `uv run pytest tests/test_audit_stack_coverage.py::test_typescript_and_react_checklists_by_extension_and_dependency` |
| AC-003 | tests/test_audit_stack_coverage.py › test_checklists_are_complete_and_cover_owasp_2025 | `uv run pytest tests/test_audit_stack_coverage.py::test_checklists_are_complete_and_cover_owasp_2025` |
| AC-004 | tests/test_audit_stack_coverage.py › test_every_supported_lockfile_gets_an_osv_audit | `uv run pytest tests/test_audit_stack_coverage.py::test_every_supported_lockfile_gets_an_osv_audit` |
| AC-005 | tests/test_audit_stack_coverage.py › test_osv_json_becomes_advisory_findings | `uv run pytest tests/test_audit_stack_coverage.py::test_osv_json_becomes_advisory_findings` |
| AC-006 | tests/test_audit_stack_coverage.py › test_npm_audit_findings_keep_their_number_under_osv | `uv run pytest tests/test_audit_stack_coverage.py::test_npm_audit_findings_keep_their_number_under_osv` |
| AC-012 | tests/test_audit_stack_coverage.py › test_dev_only_packages_give_no_finding | `uv run pytest tests/test_audit_stack_coverage.py::test_dev_only_packages_give_no_finding` |
| AC-007 | tests/test_audit_stack_coverage.py › test_without_osv_scanner_audits_fall_back_and_gaps_stay | `uv run pytest tests/test_audit_stack_coverage.py::test_without_osv_scanner_audits_fall_back_and_gaps_stay` |
| AC-008 | tests/test_audit_stack_coverage.py › test_semgrep_json_becomes_escaped_leads_per_part | `uv run pytest tests/test_audit_stack_coverage.py::test_semgrep_json_becomes_escaped_leads_per_part` |
| AC-009 | tests/test_audit_stack_coverage.py › test_a_semgrep_lead_alone_is_not_a_finding | `uv run pytest tests/test_audit_stack_coverage.py::test_a_semgrep_lead_alone_is_not_a_finding` |
| AC-010 | tests/test_audit_stack_coverage.py › test_without_semgrep_the_verdict_can_still_be_safe | `uv run pytest tests/test_audit_stack_coverage.py::test_without_semgrep_the_verdict_can_still_be_safe` |
| AC-011 | tests/test_audit_stack_coverage.py › test_audit_command_names_tools_network_and_installs | `uv run pytest tests/test_audit_stack_coverage.py::test_audit_command_names_tools_network_and_installs` |

## Must never break

- A finding written by shipped code keeps its number and its `accepted.md` acceptance on the first run after the upgrade (npm and composer advisories included).
- No code, secret or file content leaves the owner's machine; only what §1 names before the owner's yes (package names and versions to osv.dev, rule downloads from semgrep.dev).
- Nothing reads Safe to deploy while a lockfile is unaudited or a named stack has no checklist.
- Semgrep and OSV-Scanner run only on `$RUN/copy`, never on the owner's working tree, and no tool is installed by the agent.
- Every CLI failure is one `error:` line, never a traceback; tool output (rule messages, package names, file names) never forges a line in a finding, a leads file or the report.

## Failure modes

- **Untrusted input:** Semgrep and OSV JSON carry target-controlled file names, package names and messages → AC-005, AC-008 (escaping, caps, one `error:` line) and the must-never-break line on forged lines.
- **A tool fails mid-run** (offline, timeout, a lockfile OSV can't parse) → the lockfile is recorded as a failed audit (existing `audit_failures` gap); a failed Semgrep run is the AC-010 note.
- **Persisted data / upgrade:** advisory identity across the npm → OSV switch → AC-006.
- **Scale:** Semgrep on a large repo → only the parts' files, with a timeout; leads capped per part.
- **Platforms:** OSV-Scanner and Semgrep exist for macOS, Linux and Windows; install commands per platform in §1; Windows CI runs the converters' tests (they need no tool installed).

## Out of scope

- JVM and Ruby checklists (remain `no_checklist` gaps).
- govulncheck reachability; pip-audit and cargo-audit (OSV covers their lockfiles).
- `bun.lockb` (binary; OSV can't read it): stays a gap.
- Live `/audit --target` (project 3); CI.

## Review

- **Recommended and chosen:** security and code, because risk is high (untrusted target data reaching a shell, paths and the verdict) and the change adds public commands (`findings.py from-osv-scanner`, `from-semgrep`); chosen by the trigger list (L runs both without asking). Round 3 by the owner's `Review cap` answer ("One more round").
- **Verdicts:**
  - Round 1: `.sdlc/.work/findings/2026-11-23-l-audit-stack-coverage/security-r1.md` → FAIL — SEC-01, SEC-02, SEC-03, SEC-04; `code-reviewer-r1.md` → FAIL — H1, H2, H3, H4, M1, M2.
  - Round 2: `security-r2.md` → PASS; `code-reviewer-r2.md` → FAIL — M1-r2, M2-r2.
  - Round 3 (closing): `code-reviewer-r3.md` → PASS.
- **Fixed:**
  - **SEC-01 / H1** (lead check keyed on the word "semgrep"): `check --agent` and `suspects` take `--leads`; a finding naming a lead's whole rule id, "semgrep" after NFKC folding without format characters, or a lead's `path:line` needs Proof traced/proven and two `_spots`. Tests: `test_a_lead_named_by_rule_id_or_disguised_word_needs_a_trace`, `test_a_finding_at_a_lead_spot_needs_a_second_spot`.
  - **SEC-02 / H2** (target file names on the Semgrep shell line; offline flag composed from prose): `scope.py` emits the `semgrep` step (scans `.` in the copy) and each OSV audit's `step_offline`. Test: `test_scope_emits_the_semgrep_and_offline_steps`, `test_audit_command_runs_only_scripted_steps`.
  - **SEC-03 / M8** (unrated advisories didn't block): worst rating wins, `MAL-` critical, unrated high. Test: `test_malicious_and_unrated_advisories_block`.
  - **SEC-04 / M3** (id-less findings moved to fixed): kept open while their package is reported; "superseded" only for npm's `see npm audit` entries. Tests: `test_an_id_less_finding_stays_open_while_osv_reports_its_package`, `test_a_fixed_advisory_moves_to_fixed_while_its_package_has_another`.
  - **SEC-05 / M5** (target `osv-scanner.toml` hides advisories, probed: all 9 hidden): `--config scripts/osv-scanner-empty.toml` on every run.
  - **SEC-06 / M4** (failed OSV run reads clean, probed: exit 127 with `{"results": []}`): `from-osv-scanner --exit` required, only 0 or 1 accepted. Test: `test_osv_conversion_refuses_a_failed_run`.
  - **M6** (offline database unreachable under isolation): `step_offline` sets `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY` to the owner's cache folder, read before isolation.
  - **M7** (OSV rejects `go.sum`, probed): scanned through the sibling `go.mod`, `go.sum` stays the audited lockfile.
  - **H3**: `NoDefaultCurrentDirectoryInExePath` before `shutil.which`. **H4 / SEC-08**: every `error:` line escaped and capped (`_error_text`). **M1 / SEC-09**: case-sensitive, per-database advisory id formats. **M2 / M2-r2 / L1-r3 / L4-r2**: fix version is the lowest above the installed one; GIT ranges skipped; pre-release labels ranked (dev < alpha < beta < rc < release < post/patch); `v` prefixes. **SEC-07**: only all-dev packages dropped. **M1-r2**: ids kept in their own case. **M4-r2 / L2-r3 / L3-r3**: groups match records by id or alias; a group with no record is high with "see the advisory". **L4**: missing `leads_run` reads as not run. **L6**: checklist facts in rust.md, go.md, python.md, php.md.
- **Tickets:** None as follow-up work. Accepted as is: L2 (transitive npm findings flap when runs alternate between OSV and the npm fallback; both readings are recorded honestly), L5 (`host:8080` counts as a spot without `--repo`; `/audit` always passes `--repo`), SEC-R2-02 (a paraphrased lead with a spot one line off still passes `check`; the verifier still screens every agent finding), L3-r2 (a lead line cut at 500 characters can lose its spot), L1-r2/L4-r3 (the planted-tool test only bites on Windows; it runs there in CI).
- **Drift and manual checks:** every Deviations line in `.sdlc/state/2026-11-23-l-audit-stack-coverage.md` (test-order lint, scope-test PATH pinning, node.md items, one-pass build, writer subagent, README, the locked-test `--exit`/go.mod change with a fresh red at `1c57684`, Semgrep scanning `.`, the design points not built, the empty OSV config file, the review-fix test file). Manual: OSV-Scanner behaviour probed on synthetic lockfiles (exit codes 0/1/127, `dependency_groups` for dev/devOptional, `go.mod` vs `go.sum`, config override). Not exercised: a real offline run with a downloaded database.
- **Security:** M1-r3 / SEC-R2-01 (Go call analysis sending the module list while "offline"): `osv-scanner scan source --help` shows call analysis is opt-in (`--call-analysis=go` enables it), so the offline step doesn't run it; `--no-resolve` added to the database download command. No dependency audit applies (stdlib only).
- **Lessons filed:** five lines in `docs/sdlc/recurring-defects.md` (scanner exit code, target-owned scanner config, one-word output guards, unrated severity, unmatched keys moved to fixed).
