# Security and PII audit: /audit

## Why

**Request (verbatim):** "can you hunt the pii for security hardening my repos" → "beside pii, any kinds of bugs should i need to hunt before the product deploy?" → "yes, approved and add all security audit too" → "yes, start the security and PII audit".

The owner wants to check their repos (first: a Node backend and a Vue frontend) before deploy. The checks cover:
- personal data written to logs, returned beyond need, sent to third parties, stored unencrypted, or kept without a deletion path;
- authorization gaps (IDOR, missing role checks);
- injection, secrets, session and auth weaknesses;
- dependencies with known advisories.

bug-hunter today only reports bugs it can prove by running a command. Most of these findings show in the code rather than in a command's output, and the PRD lists hardening as a non-goal ([prd.md](../prd.md) Goals and non-goals). So this feature widens the product, and it has to keep what makes bug-hunter worth using: every reported item is backed by evidence that a second agent tried to disprove, and nothing is posted on its own.

**The user's words:** "add all security audit too" (the full list above, not only PII). Three decisions are the owner's and are asked in Define's approval message: the evidence rule (constitution), posting, and the access-policy input. The design below uses the recommended answer for each, marked `[recommended]`.

## Decisions

### Approaches considered

| Approach | What it is | Trade-off |
|---|---|---|
| **A. A separate `/audit` command [recommended, chosen]** | Its own agents (`security-auditor`, `finding-verifier`), checklists, finding format and output folder. It reuses `scope.py`, `throwaway.py` and `isolate.py` | More files, but security findings never mix with bug drafts or flow into public issues |
| B. A `--security` mode on `/hunt` | The same agents and draft format, with security edge inputs | Smallest change. But the draft format forces a run repro (most findings can't have one), and `/hunt-post` files public issues |
| C. Wrap external scanners (Semgrep, gitleaks, Trivy) | Fast and broad | Breaks "standard library only" and needs installs and network. It finds patterns, not authorization logic, which is this owner's biggest risk |

The deterministic parts are stdlib scripts, tested per constitution IV: the secrets scan, the finding format, numbering, the report, the dependency-audit conversion, security-first ordering and checklist choice. The judgement parts are agents: authorization, PII flows, injection reachability, and disproving a finding.

### The flow

`/audit [paths…] [--max N]`, run from the target repo:

1. **Scope.** `scope.py "$REPO" --focus security`:
   - parts with security keywords in their path come first;
   - the file set widens to config and schema files (below);
   - each part gets `checklists`;
   - `audits` lists the dependency audit steps.
2. **Ask.** Show the cost and wait for the owner's yes:
   - auditors × 100k tokens, plus about 30k per agent finding to verify;
   - the parts `--max` leaves out;
   - that the dependency list is sent to the npm or Packagist registry;
   - the trust warning;
   - whether the owner's policy file was found (below).
3. **Copy.** `throwaway.py` makes one copy for the command's own steps: the secrets scan and the dependency audits, behind `isolate.py`.
4. **Secrets.** `secrets_scan.py <copy>`, then `findings.py from-secrets-scan` writes findings to scratch. They're `proven` with the scan as evidence, and need no verifier: a script found them deterministically.
5. **Dependencies.** Run each `audits` step, then `findings.py from-npm-audit` / `from-composer-audit` writes `advisory` findings to scratch. No verifier.
   - A run counts as successful when it prints valid JSON with the expected keys, whatever the exit code: npm and composer exit non-zero when they find advisories.
   - Anything else is reported as "audit failed: <first stderr line>", for example offline, or a private registry whose token `isolate.py` removed.
6. **Audit.** One `security-auditor` per part, all at once. Each returns up to 8 findings and a PII-inventory block.
7. **Verify.** One `finding-verifier` per agent finding, all at once. A `CONFIRMED` verdict keeps the finding; `NOT CONFIRMED` and `CANNOT CHECK` drop it, and it's listed in the report with the reason.
8. **Write.** `findings.py check` on each kept finding, then dedupe (below). Then `findings.py next` numbering into `~/.bug-hunter/<host>/<owner>/<repo>/audit/NN.md` (folder mode 0700, files 0600), then `findings.py inventory` and `findings.py report`, which writes `REPORT.md`.
9. **Report.** The `REPORT.md` path, counts by severity, and the top findings. Nothing is posted.

### Finding format (`findings.py check`)

```
# <title: what's wrong, where>

**Severity:** critical | high | medium | low
**Category:** authz | injection | secrets | session | pii-logged | pii-exposed | pii-third-party | pii-storage | pii-retention | dependency | config
**CWE:** CWE-<n>
**Proof:** proven | traced | advisory

## Where
- `path:line` (one per hop: source, through each step, to sink)

## Evidence
<fenced code: quoted code for each hop, or the command and its output>

## Impact
## Fix
```

`check` also rejects a finding whose text matches any secret pattern. Secret values must never be written, and agents are told to redact values as `<redacted>`.

### Proof and severity

- **`proven`:** a repro ran in the throwaway copy (for example, calling a handler directly without the role and seeing another user's data), or a script found it.
- **`traced`:** a source-to-sink path, each hop as `path:line` with the code quoted. A traced finding can be any severity. The table shows Proof next to Severity, so the owner can see which findings rest on reading the code.
- **`advisory`:** from npm's or Packagist's advisory database. Severity maps critical→critical, high→high, moderate→medium, low/info→low. The CWE is the advisory's own, else `CWE-1395` (dependency on a vulnerable third-party component).
- **Severity guidance in `security/generic.md`:**
  - critical: unauthenticated access to other users' data, or remote code execution;
  - high: authenticated IDOR, injection, or a live secret;
  - medium: PII logged or sent to a third party without need;
  - low: hardening gaps.

### Agents

Both are read-only on the repo, use the fail-closed `isolate.py` line, and run code only in their own `throwaway.py` copy.

**`security-auditor`** gets:
- its part's files, `checklists`, the PII definition, the known list and the owner's policy if found;
- the Bash rule from `/hunt`.

It may read **any file in the repo** to follow a hop (routes, middleware, services, models, logger and SDK calls cross folders), but finds problems only in code that its part's files reach. It returns:
- up to 8 findings, in the format above;
- a `=== PII INVENTORY ===` block: one line per personal field, `field | where defined (path:line) | logged | returned | sent to | stored (encrypted?) | deletion path`, each claim with a `path:line`.

The auditor may read the repo's committed `.env`, config and fixture files (secrets live there), but never pastes a value; it writes `<redacted>`. The rule against reading the owner's own dotfiles and credentials outside the copy stays.

**`finding-verifier`** gets the finding alone, plus `REPO`, `PLUGIN` and `SCRATCH`, none of the auditor's reasoning, and the owner's policy if found. Its job is to **disprove** the finding:
- re-read each cited `path:line`;
- search the whole repo for a control that refutes it: global middleware, a guard elsewhere, an ORM scope, a sanitizer, a route marked public in the policy;
- re-run a `proven` repro.

It ends with `VERDICT: CONFIRMED`, `VERDICT: NOT CONFIRMED — <the refuting control, path:line>` or `VERDICT: CANNOT CHECK — <why>`. The budget is about 30k tokens per finding.

### What `--focus security` scans and which checklists apply

- **File set.** Source files as today, plus `.sql`, `.prisma`, `.graphql`, `.gql`, `.yaml`, `.yml`, `.toml`, `.ini`, `.conf`, `.html`, `Dockerfile`, `docker-compose*`, `nginx*.conf`, `.env*` (except `.env.example` and `.env.sample`), and `migrations/` folders. Tests stay out. Lockfiles and `docs/` are out (lockfiles go through `audits`).
- **Order.** A stable sort: parts whose path has a security keyword come first. The keywords are auth, login, session, token, user, account, admin, role, permission, route, router, controller, middleware, handler, api, model, schema, db, migration, log, payment, upload, webhook, config and env.
- **Checklists per part.** From its files and its nearest tracked `package.json`:
  - `generic` and `pii` always;
  - `node` for parts with node-stack files;
  - `vue` when the part has `.vue` files or its nearest `package.json` depends on `vue`;
  - other stacks get generic and pii only in v1.

  The rule lives in `stacks.json` (`security_checklists`).

### Dedupe, the known list, and cost

- **Dedupe.** Findings are deduped on (category, CWE, root-cause `path:line`), where the root cause is the place to fix it. A systemic issue such as "no auth middleware on the admin router" is one finding, with every affected route listed under Where. Each auditor returns at most 8 findings.
- **Known list.** For `/audit`, it is the titles in `audit/` only (`known.py --audit`). There's no `gh issue list` call, so vulnerabilities are never cross-referenced with public issues. Findings in `audit/` stay until the owner deletes them; `REPORT.md` covers every file there.
- **Cost.** `--max` caps auditors. Verifiers are bounded by 8 findings per auditor, and the cost message shows the worst case: `--max` × 8 × 30k.

### The owner's policy file `[recommended]`

An optional `~/.bug-hunter/<host>/<owner>/<repo>/policy.md`, outside the repo, that the owner writes. It holds:
- the roles, and who may see whose data;
- the routes that are public by design;
- extra fields that count as personal data for this business.

Agents use it when it's there. Without it, they use the checklists' defaults, and any authz finding that rests on an assumption ("this route looks like it should need login") says so in Impact and is capped at medium. `REPORT.md` says whether a policy was used.

### Posting `[recommended]`

Report-only in v1: nothing is filed, and no audit step runs `post.py`, `gh issue` or `gh api`. `post.py` refuses any file that has a `**Proof:**` line, so an audit finding can't be filed as a public issue even if someone points it at `audit/`. Filing private security advisories is a later feature.

### Constitution and PRD `[recommended]`

- Amend Principle I, through `sdlc:project-constitution`, to version 1.1.0. Bug drafts keep "proof by a run command". Audit findings need evidence that a separate verifier, given the finding alone, failed to disprove: a run repro, a script's output, a cited trace, or an advisory record.
- The PRD moves "security and PII findings" into goals, and keeps "posting audit findings" a non-goal.

### Secrets scan details (calls made)

- **What it scans:** tracked files in the copy, plus the repo's untracked but present `.env*` files. Those are listed separately as "local only, not committed", with severity low unless they're committed.
- **What it skips:** binaries, files over 1 MB, non-UTF-8 files, symlinks, and `node_modules`/`vendor`.
- **Patterns:** they live in `scripts/secret_patterns.json`, a copy of sdlc's guardrail patterns plus a private key header, `scheme://user:pass@host`, and `.env` assignments of `*_SECRET`/`*_TOKEN`/`*_KEY`/`PASSWORD`. A test keeps the guardrail subset in sync with `.claude/hookify/sdlc-secret-values.md`.
- **Output:** `path`, `line`, `pattern` and the match length. No preview characters, for every pattern.
- **Severity:** critical for a live cloud or payment key, high otherwise. A match in a test or fixture folder, or one that's an obvious placeholder (`xxx`, `changeme`, `example`), is low.

### Goals, non-goals, anti-goals

- **Goals:**
  - authz, injection, secrets, session, config and PII findings, each with `path:line` evidence that a second agent failed to disprove;
  - a PII inventory;
  - npm and composer dependency advisories;
  - cost shown and capped.
- **Non-goals:** fixing; posting; scanning running environments; compliance sign-off; style; dependency audits for other stacks in v1.
- **Anti-goals:**
  - guesses reported as findings;
  - a secret's value in any output;
  - findings in public issues;
  - pattern-hit floods without an impact.

**Proposals not asked for:** private security advisory filing (dropped for v1).

## Acceptance criteria

- **AC-001** prd.md §Core capabilities 1: Given a repo, when `scope.py --focus security` runs:
  - security-keyword parts come first, stable within each group, and `--max` keeps the first N of that order;
  - the file set includes the config and schema types and excludes tests, lockfiles and `docs/`;
  - each part has `checklists` (`generic`, `pii`, plus `node`/`vue` by the rule);
  - without `--focus`, output is unchanged.
- **AC-002** Given tracked npm and composer lockfiles, when `scope.py` runs, then `audits` lists `{dir, command, step}` (`npm audit --omit=dev --json`, `composer audit --format=json`), with `installs`' safe-folder and fixture rules, and `[]` otherwise.
- **AC-003** Given secrets in source, committed and untracked `.env` files, CRLF files and fixtures (each pattern in `secret_patterns.json`), when `secrets_scan.py <repo>` runs, then it prints JSON findings with `path`, `line`, `pattern`, `length`, `committed` and `severity`, and no value or part of one:
  - skipped files are skipped;
  - a clean repo gives `[]`;
  - the guardrail patterns match `.claude/hookify/sdlc-secret-values.md`.
- **AC-004** When `findings.py check <file>` runs, then it exits 0 for a finding in the format above (CRLF too), and exits 1 naming each problem for a missing or invalid field, empty section, no `path:line` in Where, no code block in Evidence, or any text matching a secret pattern.
- **AC-005** When `findings.py dir <repo>` and `next <dir>` run, then the folder is the drafts folder's sibling `audit/`, created with mode 0700, and numbering follows `drafts.py`'s rules.
- **AC-006** When `findings.py from-secrets-scan`, `from-npm-audit` or `from-composer-audit` runs on its JSON (including empty, malformed, npm 6 and npm 7+ shapes, and missing keys):
  - it writes one finding per secret or vulnerable package that passes `check`, with the severity and CWE mapping above;
  - on malformed input it exits 1 with a one-line message.
- **AC-007** Given a folder of findings and inventory blocks, when `findings.py inventory` and `report <dir>` run, then `REPORT.md` holds, and is rewritten atomically with mode 0600:
  - the findings table sorted by severity then number, with Proof;
  - counts per severity and category;
  - the merged PII inventory, deduped per field;
  - the dropped "not confirmed" items with reasons;
  - the skipped parts and unaudited stacks;
  - whether a policy file was used.

  Files that fail `check` are listed as skipped.
- **AC-008** Constitution II: given a file with a `**Proof:**` line, when `post.py` is asked to file it, then it exits 1 before calling `gh`. `known.py --audit` lists `audit/` titles and never calls `gh`.
- **AC-009** Constitution I and III: `agents/security-auditor.md` and `agents/finding-verifier.md`:
  - have `name`, `description` and `tools` frontmatter, with no Edit, Write or NotebookEdit;
  - use the fail-closed isolation line and `throwaway.py`;
  - name the finding format, the three proof levels, `<redacted>` and the policy file;
  - the auditor caps at 8 findings and returns the inventory block;
  - the verifier gets the finding alone, is told to disprove it by searching the repo, and ends with one of the three verdicts.
- **AC-010** `security/generic.md`, `node.md`, `vue.md` and `pii.md` cover their core items:
  - generic: IDOR, role check, SQL injection, command injection, path traversal, SSRF, secrets, rate limit, CORS, error leaks, severity guidance;
  - node: `req.params`, middleware order, prototype pollution, JWT `alg`, `eval`, ReDoS;
  - vue: `v-html`, `localStorage`, `VITE_`/`VUE_APP_`, open redirect, route guards;
  - pii: email, phone, national id, payment card, location, health, the five PII categories.
- **AC-011** prd.md §Core capabilities: `commands/audit.md` has `description` and `argument-hint` frontmatter, and runs in this order: scope, the cost and trust question with a wait for the owner's yes, the copy, the secrets scan, the audits, the auditors, the verifiers, check, numbering, inventory and report. It never runs `post.py`, `gh issue` or `gh api`.
- **AC-012** The constitution is at 1.1.0, with Principle I covering audit findings. The PRD lists security and PII findings under goals and keeps posting them a non-goal. The README documents `/audit`, the policy file and what isn't covered.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_audit_scope.py › test_focus_security_orders_widens_and_picks_checklists | `uv run pytest tests/test_audit_scope.py::test_focus_security_orders_widens_and_picks_checklists` |
| AC-002 | tests/test_audit_scope.py › test_lockfiles_give_dependency_audit_steps | `uv run pytest tests/test_audit_scope.py::test_lockfiles_give_dependency_audit_steps` |
| AC-003 | tests/test_secrets_scan.py › test_finds_secrets_without_printing_them | `uv run pytest tests/test_secrets_scan.py::test_finds_secrets_without_printing_them` |
| AC-004 | tests/test_findings.py › test_check_enforces_the_finding_format | `uv run pytest tests/test_findings.py::test_check_enforces_the_finding_format` |
| AC-005 | tests/test_findings.py › test_audit_folder_and_numbering | `uv run pytest tests/test_findings.py::test_audit_folder_and_numbering` |
| AC-006 | tests/test_findings.py › test_script_outputs_become_findings | `uv run pytest tests/test_findings.py::test_script_outputs_become_findings` |
| AC-007 | tests/test_findings.py › test_report_and_inventory | `uv run pytest tests/test_findings.py::test_report_and_inventory` |
| AC-008 | tests/test_findings.py › test_audit_findings_never_post_or_query_issues | `uv run pytest tests/test_findings.py::test_audit_findings_never_post_or_query_issues` |
| AC-009 | tests/test_plugin_files.py › test_audit_agents_are_read_only_isolated_and_adversarial | `uv run pytest tests/test_plugin_files.py::test_audit_agents_are_read_only_isolated_and_adversarial` |
| AC-010 | tests/test_plugin_files.py › test_security_checklists_cover_their_items | `uv run pytest tests/test_plugin_files.py::test_security_checklists_cover_their_items` |
| AC-011 | tests/test_plugin_files.py › test_audit_command_asks_first_and_never_posts | `uv run pytest tests/test_plugin_files.py::test_audit_command_asks_first_and_never_posts` |
| AC-012 | tests/test_plugin_files.py › test_constitution_prd_and_readme_cover_audit | `uv run pytest tests/test_plugin_files.py::test_constitution_prd_and_readme_cover_audit` |

## Must never break

- A secret's value, or any part of it, never appears in any script output, finding or report.
- Nothing posts. No audit step runs `post.py`, `gh issue` or `gh api`, and `post.py` refuses audit findings.
- The target repo is never written to. Code runs only in a `throwaway.py` copy behind `isolate.py` (constitution III).
- `/hunt`, its drafts and `scope.py`'s existing output keep working as before (new fields and flags only add).
- Scripts stay standard-library only.

## Failure modes

- **Untrusted input:** file contents and names from the target reach the scripts and agents. Scripts read with argument lists and never shell out with repo text, and audit steps use the safe-folder rule → AC-002, AC-003.
- **Large inputs:** the secrets scan skips files over 1 MB and binaries → AC-003.
- **I/O errors and partial writes:** `REPORT.md` is written atomically, and bad finding files are skipped → AC-007.
- **Malformed tool output:** dependency audit JSON can be empty, truncated, in an old shape or missing keys, and failed runs are told apart from advisories → AC-006.
- **Sensitive output at rest:** the audit folder is 0700 and its files 0600 → AC-005, AC-007.

## Out of scope

- Posting findings anywhere, including private security advisories.
- Dependency audits for pnpm, Yarn, Python, Go, Rust, JVM and Ruby; `REPORT.md` lists them as "not audited".
- Stack-specific security checklists beyond Node and Vue.
- Scanning running UAT or prod environments; container isolation; fixing findings.

## Review

- **Recommended and chosen:** security + code (high), because `Risk: high` (secrets, PII, agents running target code, a constitution change), L, and `## Public Surface` isn't empty. Chosen by the trigger list (L, self-chosen). Rounds 3 to 7 were the user's choices: "fix", then "fix until no findings", then "fix" for each later round, including the known-values redesign in round 4.
- **Verdicts:** in `.sdlc/.work/findings/2026-11-06-l-security-pii-audit/`.

  | Round | Security | Code (high) |
  |---|---|---|
  | r1 | FAIL S1, S2 | FAIL H1–H4, M1–M4 |
  | r2 | FAIL N1, S2, N3 | FAIL N1–N3 |
  | r3 | FAIL R3-1–R3-4 | FAIL N4 |
  | r4 | FAIL R4-1–R4-3 | FAIL H5, M5 |
  | r5 | FAIL R5-1–R5-3 | FAIL N1 |
  | r6 | FAIL R6-1 | FAIL B1, B2 |
  | r7 | PASS | PASS |

  Both r7 reviewers say no remaining ticket is worth another round. Dependency audit (`dependency-audit-r1.md`): not run. There are no runtime dependencies and `pip-audit` isn't installed.
- **Fixed** (each test-first, in `tests/test_findings.py`, `tests/test_secrets_scan.py`, `tests/test_audit_scope.py` or `tests/test_plugin_files.py`):
  - **Secrets reaching output (S1, S2, N1/N3 of r2, R3-x, R4-1, R4-2, R5-1, R5-2, R6-1):**
    - Shape-guessing secrets in free text kept trading leaks for rejected findings. Round 4 replaced it: `secrets_scan.py --fingerprints` hashes every found value, its 8-character slices and its 12-character single-case slices into the private scratch folder.
    - `findings.py check`, `inventory` and `report` withhold or reject any text holding a known value at any position, a slice of one, a vendor-shaped key (with JWT, masked and cut-short forms), or a mixed-case base64 key-body line.
    - Key bodies are fingerprinted in every layout: PEM, legacy encrypted, one-line with `\n` escapes, and quoted and joined in code.
    - A value is a placeholder only if it wholly is one.
  - **Agent findings screened before verifiers (S3), and audits that fail reported, not read as clean (H1).**
  - **Composer:** `audit --no-plugins --no-scripts` (S6).
  - **Lockfiles kept out of the audit file set (H2), and malformed meta and unreadable files handled without tracebacks (H3, H4).**
  - **Ordinary code passes `check` (M1, N4, H5, M5):** `:=`, `===`, `=>`, `key_size=1024`, `TOKEN_TTL=3600`, `sk-proj-...`.
  - **Inventory:** header and outer pipes handled, and earlier runs merged (M2, L1).
  - **npm fix advice names the package to upgrade (M3).**
  - **Re-runs deduped on the root-cause `path:line`, with Where lines merged (M4, N2).**
  - **Scanner:** `.env` files inside ignored folders are scanned (N1), trivial config values aren't secrets, and `/audit` cleans its scratch folder on any stop.
- **Tickets:**
  - Key bodies written with a code prefix (`b"…"`, a leading `+`) aren't fingerprinted. A whole 60+ character line is still caught.
  - A bare key line inside a key body is fingerprinted but not reported (T14).
  - Pieces under 16 characters in `\/`-escaped one-line keys.
  - A key's short last line.
  - `key-fragment` needs a digit.
  - `$word` values in `.env` are read as references.
  - Placeholder words at the start or end of a real passphrase.
  - `order-123`-style values flagged as credentials.
  - Matching cost on very large inputs.
- **Accepted residuals** (owner-approved, in the README):
  - a secret the scan never saw with no known shape, and personal data: both guarded only by the agents' `<redacted>` rule;
  - values deliberately not fingerprinted: under 6 characters, numbers, booleans, URLs and lowercase paths, letters-only words under 12 letters;
  - fragments under 16 characters.
- **Drift and manual checks:**
  - Every `## Deviations` line in the state file. Of note:
    - the secrets scan reads the repo, not the copy;
    - `findings.py check` runs before the verifiers;
    - `findings.py dedupe` was added;
    - the known-values design;
    - `.claude/rules/plugin-prompts.md` was updated to match constitution 1.1.0.
  - No `manual` ACs. A live `/audit` on a real repo hasn't been run; it's the first run after merge.
- **Security:**
  - No open high or critical security findings, and no secrets in the diff. The repo's own secret guardrail blocked key-shaped test data, so tests build fake secrets at run time.
  - The fingerprint file holds hashes of short slices, which can be guessed. It is kept 0600 in the private scratch folder and deleted at the end of every run.
- **Lessons filed:** [knowledge/gotchas/detecting-secrets-in-free-text.md](../../../knowledge/gotchas/detecting-secrets-in-free-text.md), [recurring-defects.md](../recurring-defects.md)
