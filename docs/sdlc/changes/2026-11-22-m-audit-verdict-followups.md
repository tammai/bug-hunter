# /audit verdict follow-ups: facts a later run learns, the upgrade run, and git calls a target can't steer

## Why

**Request (verbatim, `docs/sdlc/todo.md`):** "`/audit` verdict follow-ups, from the reviews of 2026-11-20-m-audit-verdict", with 11 sub-items:

- R3-3 and SR3-3: an acceptance written for a finding's lower severity keeps accepting it after a `severity now` raise. Show each accepted number's current severity in the Accepted list.
- R3-5 and SR3-8: a secret raised by a later commit still reads "in a local file, not committed" in its title and Impact. Add "since committed" in the report.
- Other facts frozen at first sight:
  - R3-6: "no fix known" after a fix is released;
  - SR3-4: a secret first seen after `git rm --cached` is rated low for good, though `_in_history` could raise it.
- N4, N8 and SR2-9: on the transition run after the upgrade, a legacy (no-id) secret can absorb a rotated key at the same path, or two same-shape keys in one file.
- M6: npm advisory identity depends on the order of `via` (unconfirmed).
- N9: `recheck` without `--repo` skips the git-history check.
- N11: `secret-id.key` can't be made on a filesystem without hard links (unconfirmed).
- N12, SR2-5 and SR3-2: PII inventory cells and the older git calls in `scope.py` and `secrets_scan.py` aren't hardened like the new code (control characters, an inherited `GIT_DIR`).
- S6 and SR3-6: a hostile target repo's git config. `git status` filters and a treeless partial clone's lazy fetch can run its programs (unconfirmed).
- S8: agents could edit `accepted.md` or the audit folder during a run, and nothing detects it.
- F3: split `test_orphaned_advisories_and_accepted_md_edge_lines` into one behaviour per test.

The verdict shipped in [2026-11-20-m-audit-verdict](2026-11-20-m-audit-verdict.md) is only as good as the facts it reads. Its three review rounds left these as tickets: places where a later run's facts don't reach the report, where the upgrade run merges two secrets, or where the target repo or an agent can steer what the verdict reads. Each one can make a report wrong, mislead the owner, or let the target run a program before the owner has agreed to anything. The knowledge doc [audit-facts-frozen-at-first-sight](../../../knowledge/gotchas/audit-facts-frozen-at-first-sight.md) names the class.

### Proof (each unconfirmed item was probed before this record was written)

- **M6, confirmed.** An npm finding written from `via: [A]` is moved to `fixed/` ("no longer reported by the dependency audit") when the next audit gives `via: [B, A]`, though advisory A still applies. Probe: `from-npm-audit`, then `recheck --found --audited package-lock.json`. Root cause: `_from_npm_audit` keeps only `via[0]`'s URL as the identity (`findings.py:273-281`).
- **S6, confirmed.** Take a repo whose `.git/config` sets `filter.x.clean` to a marker command, with `* filter=x` in `.gitattributes` and a tracked file whose stat changed. A plain `git -c core.fsmonitor=false status --porcelain` runs the marker. That is what `scope._coverage` runs in §1 of `/audit`, before the owner says yes. Blanking that driver's `clean` and `process` through config stops it, and a `required` driver then makes status fail. Root cause: status re-hashes stat-dirty files through the configured clean filter.
- **SR3-6, confirmed.** Make a `--filter=tree:0` clone whose `remote.origin.uploadpack` is a marker script. `git --literal-pathspecs rev-list --all -1 -- d/.env` runs the marker. With `GIT_NO_LAZY_FETCH=1` it doesn't, and it still exits 0 with a commit, so the safe answer ("in history") holds. Root cause: path-limited `rev-list` fetches missing trees from the promisor remote.
- **N11, from the code.** `_id_key` catches only `FileExistsError` from `os.link`. The `OSError` a filesystem without hard links raises (some network or synced folders; FAT and exFAT also lack Unix modes, so the key's privacy check refuses them anyway) makes every scan end with "can't use the id key". The test makes `os.link` raise `EPERM`.
- **R3-3, R3-5, R3-6, SR3-4, N4, N8, SR2-9, N9, N12, SR2-5 and SR3-2** were traced by the reviewers with `file:line`, in `.sdlc/.work/findings/2026-11-20-m-audit-verdict/` (git-ignored; the traces are summed up in that change's Review). Each AC's test proves its item failing first.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| **R3-3:** each Accepted line shows the finding's current severity, `- 02 (critical) until …`. When a later run raised it, the line says so: `(critical, raised from medium since it was first found)`. Acceptances carry no date of writing, so whether one predates the raise can't be known. The acceptance still applies. | The finding blocking again after a raise until it is re-accepted (SR3-3's first option) | The todo names this fix. Blocking again needs a re-acceptance syntax that names the severity, which is a design choice for the owner. Recorded as a proposal below. |
| **R3-5:** when a secret's evidence says `committed=false` but a status line says `seen committed`, the report's Blocking line and table title add ` (since committed)`. The finding file isn't touched. | Rewriting the title or Impact | Evidence is never rewritten (Must never break). |
| **R3-6:** `dedupe` appends `**Status (date):** fix now <fix text>` to the earlier advisory when the re-found one's `fix:` line differs from the latest one. The report reads the latest fix line, so "no fix known" goes once a fix is released. Severity still only rises. | Lowering a severity the registry revised down | One-way is the safe direction (R3-6 agrees). `SCRIPT_ONLY` already refuses `**Status (` in agent text, so an agent can't plant the line. |
| **SR3-4:** `secrets_scan.py` treats a local (untracked or ignored) env file as committed **only when git definitely says** its path is in history: `rev-list` exits 0 with a commit. Then the finding is `committed: true` at the pattern's severity, and its title reads "in a local file whose path is in git history". A git failure leaves it local and low, as today. | Raising whenever `_in_history` returns True | `_in_history` returns True when git fails, which is right for "don't mark fixed" but would wrongly raise every local secret for good. The path being in history doesn't prove this value was: a `.env` committed once with dummy values and filled in later blocks until accepted. **The owner chose this (2026-11-22).** |
| **N4, N8 and SR2-9, one rule for the legacy key** (path, pattern and length, used only by findings written before ids): an earlier legacy finding takes a produced finding's id only when the pairing is unambiguous. That means exactly one produced finding has its legacy key, or exactly one of them sits at the legacy finding's own line. Otherwise no id is recorded, and the produced findings aren't deduped into it, so they get their own numbers. A legacy finding accepted as `rotated` in `accepted.md` never answers to its legacy key, in `recheck` or in `dedupe`. A new key at that path is then a new, blocking finding. | Adding the line to the legacy key | A line drift on the upgrade run would then give every moved legacy secret a new number. The pairing rule keeps H1's case: one unrotated legacy secret keeps its number. |
| **M6:** `from-npm-audit` writes one finding per advisory object in `via`. Each finding carries that advisory's own title, CWE, URL and severity, falling back to the package's. A package whose `via` holds only names (it's vulnerable through another package) stays one finding, as today. | Identity by the *set* of URLs | A set changes when a second advisory appears, so the earlier finding would still be fixed wrongly. One finding per advisory is what `from-composer-audit` already does. A finding written today (from `via[0]`) keeps its number: its URL is still one of the new findings' identities. |
| **N9:** `recheck` without `--repo` never fixes a secret whose evidence says it was never committed. It stays open, as when git can't answer. | Making `--repo` required | Required would change what many existing test calls exercise, since the advisory branches also decide "gone" from `--repo`. Fail-closed is the smaller change. `/audit` always passes `--repo`. One existing test expected the old fixing and now passes a real repo (a recorded test change). |
| **N11:** when `os.link` fails with an `OSError` other than `FileExistsError`, the key is published with `os.rename` of the fully written, fsynced temp file, but only if no key exists yet. Known narrow window: two first runs racing on such a filesystem can both see no key, and on POSIX the later rename replaces the earlier key, so the earlier run's ids differ from every later run's once. | `O_CREAT\|O_EXCL` and then write | That leaves a window where a kill gives a short key. `test_the_id_key_is_refused_unless_private_and_never_left_short` must stay true. |
| **N12, SR2-5, SR3-2 and SR3-6: one git helper for every git call in the three scripts.** `secrets_scan.run_git` drops `_REPO_VARS` (imported from `throwaway.py`), sets `GIT_NO_LAZY_FETCH=1`, and passes `--no-optional-locks -c core.fsmonitor=false`. `scope._tracked_files`, `scope._git_out`, `secrets_scan._git_names` and `findings._in_history` all use it. The PII inventory escapes control characters in every cell (`_printable`) when it merges. | Dropping every inherited `GIT_*`, as `isolate.py` now does | `/audit` runs the scan inside `isolate.py`, which exports `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_NOSYSTEM`; a wider strip would undo those. `_REPO_VARS` is what the recurring defect names. |
| **S6:** before `git status`, `scope.py` lists the filter drivers the target's own config defines, at local or worktree scope, includes followed (`git config --show-scope -z --name-only --get-regexp ^filter\.`; reading config runs nothing). It blanks each driver's `clean`, `process` and `smudge` for that one command, passed as `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n`, so a name with `=`, a space or a dot can't break the override. A blanked filter that changes content makes the file read dirty, and a `required` one makes status fail. Both give a gap ("uncommitted changes" or "couldn't tell"), never a run program. | Blanking global and system drivers too; not running status at all | The owner's own drivers (git-lfs in `~/.gitconfig`) are trusted, and blanking them would make every LFS repo read dirty. Without status there's no dirty fact, so no repo could read Safe. |
| **S8:** `findings.py seal <audit>` prints one SHA-256 over `accepted.md`, `policy.md` and every `audit/NN.md`, `fixed/NN.md` and `inventory.md`. Each file is length-framed by name and bytes. `/audit` runs it at the end of §1, before any agent, and keeps the hex in its own context, not in a file agents can reach. §6 now reaps background processes first. `recheck --seal <hex>` then refuses, with one `error:` line and nothing moved, when the folder changed, and `/audit` stops and tells the owner. | Detecting it only in the report | By the report, `recheck` has already acted on tampered files. Refusing before anything moves leaves the folder as the agents left it, for the owner to look at. The owner chose to build it in this change (2026-11-22). |
| **F3:** the test splits into three, one behaviour each: an orphaned advisory is CANNOT CHECK, `accepted.md` takes a BOM and list markers, and npm 6's `<0.0.0` means no fix. | — | Test-only. |
| **The build runs inline,** in one session, in this order: report-only items (R3-3, R3-5, R3-6), the git helper and S6, SR3-4, identity (M6, N4/N8/SR2-9), N9, N11, S8, then F3 and docs. | Parts in fresh sessions | About 7 files. If context runs short, S8 is the first to become a ticket (question 3). |

**Proposals not asked for (both dropped by the owner, 2026-11-22):**

- An accepted finding raised since its acceptance blocks again until re-accepted (SR3-3's stronger option).
- S6's submodule half: a submodule's own `.git/config` filters can still run under `--ignore-submodules=none`. See Out of scope.

**Owner's answers at the approval (2026-11-22):** approve; SR3-4 as above (committed at full severity only on a definite yes from git); S8 built in this change; R3-3 shows the current severity and the raise and keeps accepting.

## Acceptance criteria

- **AC-001** (R3-3) Given an accepted finding, when the report is written, then its Accepted line shows its current severity. When a later run raised it, the line names both severities and says it was raised since the finding was first found.
- **AC-002** (R3-5) Given a secret first written "in a local file, not committed" and since seen committed, when it blocks, then its Blocking line and its findings-table title say "(since committed)", and the finding file is byte for byte unchanged apart from status lines.
- **AC-003** (R3-6) Given an earlier advisory written "no fix released yet", when a later audit reports it with a fix and dedupe runs, then a `fix now` status line is appended and the Blocking line no longer says "no fix known". An agent finding carrying a `fix now` line fails `check --agent`.
- **AC-004** (SR3-4) Given an ignored `.env` whose path was committed and then removed with `git rm --cached`, when the secrets scan runs, then the finding is `committed: true` at the pattern's severity, titled "in a local file whose path is in git history". When git fails, the finding stays local and low.
- **AC-005** (N4, N8, SR2-9) On the run after the upgrade:
  - a legacy secret accepted as `rotated` doesn't take a new key's id at its path, and the new key gets its own number;
  - with two same-shape keys in its file, a legacy secret takes only the id at its own line;
  - with an ambiguous pairing, it takes none;
  - an unrotated, unambiguous legacy secret still keeps its number (H1).
- **AC-006** (M6) Given an npm finding written from `via: [A]`, when the next audit gives `via: [B, A]`, then the earlier finding stays open with its number (and its acceptance), and B is a new finding. A finding written by today's converter still matches.
- **AC-007** (N9) Given an open secret whose evidence says it was never committed, when `recheck` runs without `--repo` and the scan no longer finds it, then it stays open.
- **AC-008** (N11) Given a filesystem where `os.link` raises `OSError` (not `FileExistsError`), when the scan makes `secret-id.key`, then it succeeds with a private 32-byte key and leaves no temp file.
- **AC-009** (N12, SR2-5, SR3-2) Given a caller with `GIT_DIR` (and the other `_REPO_VARS`) pointing at another repo, when `scope.py` and `secrets_scan.py` run, then they read the target repo. Given an auditor's inventory cell with ESC or another control character, when the inventory is merged and the report written, then no control character reaches either file.
- **AC-010** (S6, SR3-6) Given a target whose own git config defines a `clean` or `process` filter (with a name holding `=`, a space or a dot), when `scope.py --focus security` runs, then no filter program runs, and `dirty` is what the files show with those filters blanked (false when they'd change nothing), never a crash. A `required` driver gives null. The owner's global drivers aren't blanked. A treeless partial clone's history lookup runs nothing from its remote config and never answers "not in history".
- **AC-011** (S8) Given `findings.py seal` run before the agents, when `accepted.md`, `policy.md`, an `NN.md`, a `fixed/NN.md` or `inventory.md` is added, changed or removed before `recheck --seal`, then `recheck` prints one `error:` line, exits 1 and moves nothing. Unchanged, it runs as before. `/audit` seals as the first step after the owner's yes and before any agent, reaps before `recheck`, passes `--seal`, and the README documents it.
- **AC-012** (review r1 SEC-1, H1) Given a git older than the floor (2.31 for config by variable, 2.45.1 for `GIT_NO_LAZY_FETCH`), when the target's own config defines a filter driver, then `scope.py`'s dirty check gives null without running status. On a partial clone, the history lookup answers "can't say". On every git, `run_git` refuses every transport (`GIT_ALLOW_PROTOCOL` naming no protocol, plus `protocol.allow=never`), even when the target's config allows `file` or `ext` by name, so no fetch runs the target's `uploadpack`. `browser.py`'s one git call ignores an inherited `GIT_DIR` and `GIT_WORK_TREE` (review r2 H1, H-A, M-A).
- **AC-013** (review r1 M1, L6; r2 H2, H-B) Given two open legacy secrets sharing one key, A at line 3 and B at line 7, when the scan finds only the line-3 secret, then A takes its id, B takes none and stays open, and no produced secret is paired with two findings, in that run or the next one (B's file stays byte for byte unchanged). A rotated, never-committed legacy secret that is fixed says it was rotated and that the key now at that path is a separate finding.
- **AC-014** (review r1 SEC-2) Given the seal, when `accepted.md` or `policy.md` changes after `recheck`, then `dedupe --seal` and `report --seal` each print one `error:` line and exit 1, without writing.
- **AC-015** (review r2 U1) Given a target with a submodule whose own config defines a clean filter, when `scope.py --focus security` runs, then no filter program runs, `coverage.submodules` names the submodule, and the report lists "submodule not checked for uncommitted changes" as a gap.
- **AC-016** (review r2 M1) Given a local `.env` with a secret whose history git can't answer (an old git on a partial clone), when the scan runs, then the finding says `history_unknown`, and a report given that path in `--meta history_unknown` lists "couldn't tell whether git history holds" it as a gap.
- **AC-017** (review r3 R3-H1) Given a never-committed pre-id secret whose legacy key a produced secret still shares (AC-013's B, or one whose same-shape secrets got their own numbers), when `recheck --repo` runs on later runs, then it stays open and untouched, never moved to `fixed/` as "no longer found".
- **AC-018** (review r3 M-1) Given a shallow clone, when the history of a path is asked, then the answer is "can't say", the scan marks a local `.env` `history_unknown`, and neither its title nor its Impact claims it was never committed (review r4 L-2); its evidence line is unchanged.
- **AC-019** (review r4 M-A) Given history hidden by a replace graft or an `info/grafts` file, when the history of a path its hidden commits held is asked, then the answer is never "not in history".
- **AC-020** (review r4 L-3, L-4, L-5) Given every git call timing out, then `run_git` gives code 124, `in_history` "can't say", `browser._tracked` None, and `secrets_scan.py` and `scope.py` print "error: git timed out on <repo>". `browser.py`'s copied repo-variable set equals `throwaway._REPO_VARS`.

F3 (a test split) has no AC: it changes no behaviour. `verify.py` checks it through the full suite.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_findings.py › test_accepted_lines_show_the_current_severity_and_a_raise | `uv run pytest tests/test_findings.py::test_accepted_lines_show_the_current_severity_and_a_raise` |
| AC-002 | tests/test_findings.py › test_a_secret_committed_since_says_so_in_the_report | `uv run pytest tests/test_findings.py::test_a_secret_committed_since_says_so_in_the_report` |
| AC-003 | tests/test_findings.py › test_a_fix_released_later_reaches_the_report | `uv run pytest tests/test_findings.py::test_a_fix_released_later_reaches_the_report` |
| AC-004 | tests/test_secrets_scan.py › test_a_local_env_whose_path_is_in_history_counts_as_committed | `uv run pytest tests/test_secrets_scan.py::test_a_local_env_whose_path_is_in_history_counts_as_committed` |
| AC-005 | tests/test_findings.py › test_legacy_secrets_pair_only_unambiguously_and_never_when_rotated | `uv run pytest tests/test_findings.py::test_legacy_secrets_pair_only_unambiguously_and_never_when_rotated` |
| AC-006 | tests/test_findings.py › test_npm_advisory_identity_survives_a_reordered_via | `uv run pytest tests/test_findings.py::test_npm_advisory_identity_survives_a_reordered_via` |
| AC-007 | tests/test_findings.py › test_recheck_without_repo_never_fixes_a_local_secret | `uv run pytest tests/test_findings.py::test_recheck_without_repo_never_fixes_a_local_secret` |
| AC-008 | tests/test_secrets_scan.py › test_the_id_key_is_made_without_hard_links | `uv run pytest tests/test_secrets_scan.py::test_the_id_key_is_made_without_hard_links` |
| AC-009 | tests/test_audit_scope.py › test_git_calls_and_inventory_cells_cant_be_steered | `uv run pytest tests/test_audit_scope.py::test_git_calls_and_inventory_cells_cant_be_steered` |
| AC-010 | tests/test_audit_scope.py › test_the_dirty_check_runs_no_program_from_the_target_config | `uv run pytest tests/test_audit_scope.py::test_the_dirty_check_runs_no_program_from_the_target_config` |
| AC-011 | tests/test_findings.py › test_recheck_refuses_an_audit_folder_changed_during_the_run | `uv run pytest tests/test_findings.py::test_recheck_refuses_an_audit_folder_changed_during_the_run` |
| AC-012 | tests/test_audit_scope.py › test_an_old_git_fails_closed_and_no_transport_runs | `uv run pytest tests/test_audit_scope.py::test_an_old_git_fails_closed_and_no_transport_runs` |
| AC-013 | tests/test_findings.py › test_legacy_pairing_is_one_to_one_and_a_rotated_fix_says_why | `uv run pytest tests/test_findings.py::test_legacy_pairing_is_one_to_one_and_a_rotated_fix_says_why` |
| AC-014 | tests/test_findings.py › test_dedupe_and_report_refuse_a_changed_acceptance | `uv run pytest tests/test_findings.py::test_dedupe_and_report_refuse_a_changed_acceptance` |
| AC-015 | tests/test_audit_scope.py › test_submodules_are_a_gap_and_their_filters_never_run | `uv run pytest tests/test_audit_scope.py::test_submodules_are_a_gap_and_their_filters_never_run` |
| AC-016 | tests/test_audit_scope.py › test_an_unknown_history_for_a_local_secret_is_a_gap | `uv run pytest tests/test_audit_scope.py::test_an_unknown_history_for_a_local_secret_is_a_gap` |
| AC-017 | tests/test_findings.py › test_a_pre_id_secret_whose_key_is_still_produced_is_never_fixed | `uv run pytest tests/test_findings.py::test_a_pre_id_secret_whose_key_is_still_produced_is_never_fixed` |
| AC-018 | tests/test_audit_scope.py › test_a_shallow_clone_cant_say_a_path_was_never_committed | `uv run pytest tests/test_audit_scope.py::test_a_shallow_clone_cant_say_a_path_was_never_committed` |
| AC-019 | tests/test_audit_scope.py › test_replaced_history_cant_say_a_path_was_never_committed | `uv run pytest tests/test_audit_scope.py::test_replaced_history_cant_say_a_path_was_never_committed` |
| AC-020 | tests/test_audit_scope.py › test_a_git_timeout_is_cant_say_never_clean | `uv run pytest tests/test_audit_scope.py::test_a_git_timeout_is_cant_say_never_clean` |

## Must never break

- "Safe to deploy" is never written while any gap or any open, unaccepted critical or high finding exists.
- No finding, report line, status line or fixed note carries a secret the scan saw, even partly.
- A finding's evidence is never rewritten, and a finding number is never reused.
- A finding written by the shipped code keeps its number and its `accepted.md` line on the first run of this code (H1's test stays green).
- Severity only ever rises.
- Every CLI error path ends in one `error:` line, never a traceback.
- No program named by the target's git config runs from `scope.py`, `secrets_scan.py` or `findings.py`.

## Failure modes

- **Persisted data:** identity changes (M6, legacy pairing) meet findings already on disk. Covered by AC-005, AC-006 and the H1 test.
- **Untrusted input:**
  - target-chosen filter driver names → AC-010;
  - control characters in agent-written inventory cells → AC-009;
  - agent-written files in the audit folder → AC-011;
  - a `fix:` text from the registry reaches the report through `_piece`.
- **I/O errors and git failing:**
  - a git failure never raises a severity (AC-004);
  - status failing is a gap (AC-010);
  - the link fallback has no short-key window (AC-008).
- **Concurrent use:** two first runs making the key at once. The rename publishes only when no key exists, and the loser reads the winner's key (AC-008).
- **A crash mid-write:** every status line goes through `_append`, which is atomic. `seal` only reads.

## Out of scope

- Blocking an accepted finding again after a raise (proposal above).
- A submodule's own git config filters under `--ignore-submodules=none` (S6's residual). Auditors don't read submodule files (`ls-files` lists a gitlink), but `status` recurses into them. Dropped by the owner (2026-11-22).
- Lowering a severity the registry revised down: kept one-way by design.
- `drafts.py`, `oracle.py`, `isolate.py` and `contracts.py` are owned by parallel changes and aren't touched.
- `docs/sdlc/todo.md` isn't edited in this change; the orchestrator ticks the item.
