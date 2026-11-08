# bug-hunter 0.4 part 3: two-target proxy, dual repro, classify

## Why

**Request (verbatim):** implement docs/specs/rebuild-upgrade/04-bug-hunter.md, part 3 only.

Part 3 is B2 of [docs/specs/rebuild-upgrade/04-bug-hunter.md](../../specs/rebuild-upgrade/04-bug-hunter.md): `/hunt --target <rebuild> --reference <reference>` runs every repro against the rebuild and the running reference, and a script, not an agent, classifies each finding from the two results (build defect, reference defect, accepted departure, spec gap). Built on part 2 (branch `2026-11-08-m-oracle-scoping` @ 8dcab0e), after re-vendoring contracts 1.1.1.

**The user's words:** orchestrator brief (msg_670e45567da7) and answers (msg_d0c40199e049, "All as proposed"):
- Re-vendor contracts **1.1.1** byte-identical from product-rebuild `contracts/v1` (branch `2026-11-08-l-shared-contracts-v1` @ `3274d37`), MANIFEST sha256 `e385f981…de30b`; vendor-check. Done before this record (README's version line updated).
- Acceptance for this part: proxy two-target isolation test; classification table, every row; the fixture rebuild + reference pair in `tests/fixtures/` (planted build defect, shared reference defect, departure, spec gap) classified correctly. Departures (B5) come in part 5: build the fixture so part 5 can add it. No live run that spends tokens without the orchestrator's go.
- Q1 rows 2 vs 5: "wrong" means wrong by the bug bar regardless of the spec. The hunter writes `Defect: yes` under the title when the shared behaviour is wrong on its own (crash/5xx, data loss, wrong stored state); the verifier must confirm it from the output; `classify` decides by script.
- Q2: both wrong but different → `build-defect`; reference not run (proxy refusal, unreachable, account missing there) → the class B1 gives alone, `observed.reference: "not run: <reason>"`; rebuild correct → no finding; `--reference` without `--oracle` → "spec covers it" is always no.
- Q3: under `--reference`, an `Oracle: spec-gap` draft becomes `build-defect` when the reference is correct (row 1) and `reference-defect` when the reference is the same wrong (row 3).
- Q4: `finding_v1.py classify`, a deviation from B2's `findings.py classify` (that file is `/audit`'s).
- Q5: under `--reference` the repro is C4 HTTP replay (`runner: http`); the runner reuses contracts' step checker rather than copying its rules.
- Q6: one proxy process, two loopback listeners, both targets' secrets and addresses masked on both, one budget for both (doubled in the cost question), `--reference` equal to `--target` refused.
- Q7: the fixture acceptance is a pytest (no agents); row 4 is a `--departure <ID>` input to `classify`; reading `departures.yaml` stays in part 5.
- Q8: M, risk high: plan approval by the orchestrator, plus a security review.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| `live_proxy.py --reference <name>`: one process, two listeners on 127.0.0.1; a second stdout line `reference listening on <url>`; `--check` adds `reference ok: …` | A path prefix (`/ref/…`) on one listener | Separate listeners can't be crossed by any path or header; the single-target CLI and its first line stay as they are |
| The budget and rate are one shared counter across both listeners; each log line gets `"target": "rebuild"` or `"reference"` only when `--reference` is given | Two budgets | One number for the owner to approve (Q6); the report lists writes per target |
| Each listener masks every account value and the address of **both** targets | Each masks its own | A reference echoing a rebuild login (or the reverse) must not leak either |
| The proxy's own refusals (400, 403, 411, 429, 502) carry `X-Bug-Hunter-Refused: 1` | Telling a refusal from the target's own 4xx by status | `replay` must report "not run" for a refused reference, never a wrong result (Q2) |
| `--reference` requires `--target` and `--format finding-v1` | Drafts with a reference | Classes and the HTTP repro exist only in finding-v1; drafts for GitHub stay unchanged |
| Under `--reference` the hunter's `## Repro (finding-v1)` is a JSON list of C4 steps (`{request, expect}`, `expect` = what the oracle says), checked with contracts' `_check_steps`; a `## Observed (finding-v1)` JSON object holds the `replay` output against `rebuild` and `reference` | A `cli` list with a `ref_stdout` per step | C6 asks for the C4 runner format; structured results let a script classify (Q5) |
| `finding_v1.py replay --draft F --base URL` runs the steps with contracts' `_pointer`, `_rule_ok` and `_same`, accounts from `ACCEPT_ACCOUNT_<NAME>`, and prints `{"result": "pass"}`, `{"result": "fail", "step": n, "message": …}` or `{"result": "not run: …"}` | `contracts.py run-http` | `run-http` refuses a test without a criterion ID (reference-defect and spec-gap repros have none) and can't see the proxy's refusal header |
| "Same wrong" = both fail at the same step with the same message | Comparing bodies | The message holds what differs from the oracle; a generated value in it makes two equal defects look different (→ `build-defect`, the safe side) |
| `observed.rebuild` / `observed.reference` under `--reference` are the two `replay` messages (`"as expected"` for a pass) | `What happens` text | Script-produced and symmetric |
| Row 2's finding gets an extra field `propose_departure: "reference-defect-not-copied"` | Writing `departures.yaml` | B5: a hunter may propose, never write the registry; the schema allows extra fields |
| Fixture: two stdlib apps (`tests/fixtures/reference-pair/rebuild.py`, `reference.py`), a spec folder (lock, stories, `domain.md`, `departures.yaml` with D-001 for part 5) and four planted drafts | One app with a flag | Two apps keep each side readable; part 5 reads the departure already there |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** spec §B2 / §Acceptance (proxy two-target isolation): Given `live_proxy.py --target A --reference B` with different accounts, when requests go to each listener, then each reaches only its own target, in both directions: an absolute-form URI naming the other target, `Host:` or `X-Forwarded-Host:` set to the other, a `..` path, and an account that exists only on the other target never reach it; responses from either listener show neither target's account values nor addresses; each log line names its `target`.
- **AC-002** spec §B2 (writes, budget): Given a reference with `"writes": false` and a rebuild with writes allowed and `--max-requests 3`, when a POST goes to each listener, then the reference refuses it (403) and the rebuild forwards it, and once three requests are counted across both listeners the next one on either gets 429; every proxy refusal carries `X-Bug-Hunter-Refused: 1`.
- **AC-003** spec §B2: Given `--reference` naming the same target as `--target` (same name or same URL), when the proxy runs, then it prints one `error:` line and exits 1; `--check` with `--reference` prints a `target ok:` and a `reference ok:` line; without `--reference` the output is as on part 2.
- **AC-004** spec §B2 (dual repro): Given a draft whose Repro is a list of C4 steps, when `finding_v1.py replay --draft F --base URL` runs, then it prints `{"result": "pass"}` when every expect holds, `{"result": "fail", "step": n, "message": …}` at the first that doesn't (captures substituted, `ACCEPT_ACCOUNT_<NAME>` sent as a header), and `{"result": "not run: …"}` for a proxy refusal or an unreachable base; a step contracts' checker refuses gives one `error:` line and exit 1.
- **AC-005** spec §B4 with B2: Given an HTTP-repro draft with `## Observed (finding-v1)`, when `finding_v1.py render` runs, then its Steps show each request and both results, and `drafts.py check` passes it; a draft missing Observed, or with an Observed that isn't `{rebuild, reference}` results, gives one `error:` line.
- **AC-006** spec §B2 (classification table, every row) with Q1–Q3: Given the two results, the spec's cover (criterion or rule cited, or not), `Defect: yes` and an optional departure, when `classify` runs, then: rebuild wrong + reference correct → `build-defect`; same wrong + spec covers + defect → `build-defect` with `propose_departure`; same wrong + not covered + defect → `reference-defect` (route human); rebuild differs + `--departure D-001` → `accepted-departure` (route drop); same + spec covers + no defect → `spec-gap` (route rspec); both wrong differently → `build-defect`; reference not run → the B1 class; rebuild passing, or same + not covered + no defect → not a finding (one `error:` line, exit 1).
- **AC-007** spec §B4 with B2: Given a verified HTTP-repro draft and two result files, when `finding_v1.py write … --rebuild R1 --reference R2 [--oracle S] [--departure ID]` runs, then the finding has `repro: {"runner": "http", "steps": …}`, both `observed` messages, `class` and `route` from `classify`, and passes `check_finding`; a missing or non-JSON result file, or a not-a-finding case, writes nothing and prints one `error:` line.
- **AC-008** spec §B2: Given `drafts.py check --repo R --target A --reference B`, when a draft names the reference's host or holds a reference account's value, or its `Set before running:` line doesn't name `REF_BASE`, then it fails with that problem.
- **AC-009** spec §Acceptance (fixture): Given the fixture rebuild and reference apps behind the two-target proxy and the four planted drafts, when each is replayed against both and written with `--oracle`, then the planted build defect is `build-defect`, the shared reference defect `reference-defect`, the spec gap `spec-gap`, and the departure-shaped difference `build-defect` without `--departure` and `accepted-departure` with `--departure D-001`.
- **AC-010** spec §B2: `/hunt --target A --reference B --format finding-v1 --out D` checks both targets, shows both and the doubled budget before the cost question, gives agents `BASE` and `REF_BASE` only, has hunters and verifiers run every repro against both (with `Defect: yes` confirmed by the verifier), re-runs `replay` against both by script after `VERDICT: REPRODUCES`, writes findings with the two results, and reports class and route; without `--reference` nothing changes. `[manual: prompt text, checked in Review against the spec]`

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_reference.py › test_each_listener_reaches_only_its_own_target | `uv run pytest tests/test_reference.py::test_each_listener_reaches_only_its_own_target` |
| AC-002 | tests/test_reference.py › test_writes_per_target_and_one_shared_budget | `uv run pytest tests/test_reference.py::test_writes_per_target_and_one_shared_budget` |
| AC-003 | tests/test_reference.py › test_reference_flags_are_checked | `uv run pytest tests/test_reference.py::test_reference_flags_are_checked` |
| AC-004 | tests/test_reference.py › test_replay_reports_pass_fail_and_not_run | `uv run pytest tests/test_reference.py::test_replay_reports_pass_fail_and_not_run` |
| AC-005 | tests/test_reference.py › test_http_repro_renders_both_results | `uv run pytest tests/test_reference.py::test_http_repro_renders_both_results` |
| AC-006 | tests/test_reference.py › test_classification_table_every_row | `uv run pytest tests/test_reference.py::test_classification_table_every_row` |
| AC-007 | tests/test_reference.py › test_write_takes_class_from_both_results | `uv run pytest tests/test_reference.py::test_write_takes_class_from_both_results` |
| AC-008 | tests/test_reference.py › test_draft_check_hides_the_reference_too | `uv run pytest tests/test_reference.py::test_draft_check_hides_the_reference_too` |
| AC-009 | tests/test_reference.py › test_fixture_pair_is_classified | `uv run pytest tests/test_reference.py::test_fixture_pair_is_classified` |
| AC-010 | manual | prompt text: no test can run an agent; Review checks `commands/hunt.md`, `agents/bug-hunter.md` and `agents/repro-verifier.md` against spec §B2 |

## Must never break

- Without `--reference`, `live_proxy.py`, `drafts.py check`, `finding_v1.py` and `/hunt` behave as on part 2 (existing tests pass unchanged); the only proxy change visible without it is the `X-Bug-Hunter-Refused` header on the proxy's own refusals.
- `contracts.py vendor-check contracts/v1` prints `ok:` (contracts 1.1.1).
- Agents never see either target's URL or any account token; no request reaches a target except through its own listener.
- No finding is written unless its draft passed `drafts.py check` and its verifier said `VERDICT: REPRODUCES`; a finding file is never overwritten; nothing is written in the target repo.

## Failure modes

- Untrusted input (drafts and result files come from agents; responses from both targets): parsed as JSON only, never run; responses masked for both targets → AC-001, AC-004, AC-007
- A target echoing the other target's login or address → AC-001
- I/O errors (unreachable base, missing or non-JSON result file) → AC-004, AC-007
- Concurrent use (agents sharing one budget across two listeners) → AC-002

## Out of scope

- Reading and matching `departures.yaml` (part 5); browser mode (part 4).
- A live `/hunt --oracle --reference` run: only on the orchestrator's go.
- A version bump or release tag.

## Review

- **Fired and chosen:** a security review (`Risk: high`: the proxy holds account tokens, and untrusted drafts, result files and responses are parsed) and a code review (`## Public Surface` isn't `- none`). The orchestrator approved both (msg_d186240a8e49). Security ran on `sdlc:code-reviewer` (opus) with the brief's security section; code ran on the built-in `code-review` (`high --max-findings all`). There is no dependency audit, because the scripts are stdlib-only.
- **Verdicts:**
  - security: `security-r1.md` FAIL (S-1, S-2, S-6), then `security-r2.md` PASS;
  - code: `code-reviewer-r1.md` FAIL (CR-1, CR-2), then `code-reviewer-r2.md` PASS.
  - All four reports are under `.sdlc/.work/findings/2026-11-08-m-reference-classify/`.
  - The first code-review call was mis-targeted: it reviewed commit 8dcab0e (part 2) instead of this change. It wrote no report, was rerun on the working diff, and its findings on part 2's `oracle.py` go to the orchestrator as notes.
- **High findings and their fixes**, each with a failing test first, in `tests/test_reference.py`:
  - **S-1:** the two targets' masks ran one after the other, so a nested secret or a same-host address could leak. Now one masker covers both targets, longest pattern first, and maps each address to its own listener.
  - **CR-1 and CR-2:** the orchestrator's own replay sat outside the budget, and a rebuild that "didn't run" was dropped. A verified finding could be lost. Now that replay is counted in the budget, the proxy is restarted before Classify if needed, and the run has a timeout. A rebuild that didn't run gives class `environment`, routed to the orchestrator.
- **Medium and low bugs, fixed the same way:**
  - **Round 1:**
    - S-2: `replay` now goes through contracts' own `_run_steps`, with no environment proxy and redirects followed only within the base (also fixes CR-5 and CR-6);
    - S-3 and R2-4: routing-override headers are dropped when two targets run;
    - S-4: the verifier gets the draft as a file;
    - S-6 / CR-7: `--reference` without `--target` is refused;
    - S-7 and R2-8: http.server's own refusals carry the header and are logged;
    - S-8: the orchestrator's replay runs under a timeout;
    - S-9 and S2-2: output is ASCII-escaped;
    - CR-3: the finding's draft shows the fresh results;
    - CR-4: `--check` warns about accounts on only one target;
    - CR-8: loopback aliases count as one server;
    - CR-9: the docs state the localhost-writes rule;
    - CR-10: departure IDs follow C5;
    - CR-11 and R2-6: shutdown is clean;
    - CR-13 and CR-14: cleanups.
  - **Round 2:**
    - S2-1 / R2-1: a cut message keeps a digest;
    - R2-2: "request failed" is matched only in contracts' position;
    - S2-3: an address followed by a port is masked again;
    - R2-5: non-ASCII hosts;
    - R2-11, R2-14, R2-15: smaller fixes.
- **Tickets:**
  - S-5 and S2-4: no `drafts.py`-style host and login scan of a finding's `observed` and `draft` fields (messages are now capped at 500 characters with a digest);
  - S2-5: an allow-list of forwarded headers, and `%252e` double decoding;
  - S2-6: the hunter writes its draft through a quoted heredoc;
  - S2-7 and R2-10: `replay` depends on contracts' private `_run_steps`, `_Fail` and their wording, and installs a process-global opener (needs a public structured runner upstream);
  - CR-12: deduplicating the target-independent draft check;
  - R2-3: a script re-run that passes drops a verified finding, as Q2(c) decided; `flaky` would keep it, which is a question for the orchestrator;
  - R2-7: the same host and port with different base paths counts as two servers;
  - R2-9: a `--departure` is ignored silently when the reference didn't run or failed the same way;
  - R2-12 and R2-13: render's duplicated heading scan, and its double render.
- **Drift and manual checks:**
  - **Deviations:**
    - `finding_v1.py classify` instead of `findings.py classify` (Q4);
    - helper exports;
    - `replay` on contracts' `_run_steps`;
    - the `environment` class;
    - render from the fresh results;
    - the single masker and routing headers;
    - a review-fix test outside the AC table;
    - round-2 fixes.
  - **Tests:** `uv run pytest` gives 206 passed and 17 failed. All 17 are the Windows rows in `.sdlc/baseline.md` (diffed). AC-001 to AC-009 failed first, then passed.
  - **AC-010 (manual):** `commands/hunt.md` (Running reference), `agents/bug-hunter.md` (Running reference) and `agents/repro-verifier.md` were checked against spec §B2 by both review rounds. Without `--reference` their text is unchanged.
- **Lessons filed:** [recurring-defects.md](../recurring-defects.md) gets two lines: masks applied in sequence, and a verified finding dropped by a script re-run.
