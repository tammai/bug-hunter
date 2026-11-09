# bug-hunter 0.4 part 1: contracts v1, finding-v1 output, orchestrated runs

## Why

**Request (verbatim):** implement docs/specs/rebuild-upgrade/04-bug-hunter.md, part 1 only (vendor contracts v1 1.1.0; B4 --format finding-v1 --out output; B6 --yes --budget and --cost-log flags)

The spec is [docs/specs/rebuild-upgrade/04-bug-hunter.md](../../specs/rebuild-upgrade/04-bug-hunter.md) (backlog part 1: vendor contracts, B4, B6). It lets the product-rebuild pipeline run `/hunt` unattended under a budget and read its results as routable C6 findings instead of GitHub issue drafts.

**The user's words:** answers from the orchestrator (Orca, 2026-11-08), recorded here so nothing is in anyone's head:
- Vendor contracts **1.1.0** byte-identical from product-rebuild `contracts/v1` (branch `2026-11-08-l-shared-contracts-v1` @ `683e7d7`), MANIFEST sha256 `4064651b…7e59a21`; add `contracts/v1/** -text` to `.gitattributes`; vendor-check it.
- Q1 repro (user chose (a)): `{"runner": "cli", "steps": [{"command": …, "stdout": …}]}` taken by script from the verified draft's Steps, live steps with `env` names from the `Set before running:` line. bug-hunter's own shape until contracts settle `cli`; a deviation from C6's "C4 runner format". HTTP replay stays with part 3 (B2).
- Q2 severity: in finding-v1 mode only, the hunter writes `Severity: high|medium|low` under the draft title (sdlc's Severity list).
- Q3 without `--oracle`/`--reference`: `class: build-defect`, `route: sdlc`, `criterion`/`rule` null, `observed.reference: "not run: no --reference"`, `verified_by: {agent: "repro-verifier", result: "reproduced"}`; only REPRODUCES drafts are written; each file passes `check_finding` first; extra `title` and `draft` fields (the schema allows extra fields).
- Q4 budget: each hunter counts at its worst case, 100k + 5 verifiers × 20k = 200k; hunters start in scope order while the running estimate stays within the budget; the rest are reported as not run. Estimates stay in fresh tokens. `--yes` without `--budget` is refused; `--budget` without `--yes` still asks.
- Q5 cost log: one C7 line per hunter and verifier; `tokens_in`/`tokens_out` null (the host reports no split), the total in an extra `tokens_total` field (`check_cost` accepts unknown fields).

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| Vendored at `contracts/v1/`, excluded from ruff, drift test runs `contracts.py vendor-check contracts/v1` | Editing the vendored files to pass lint; no drift test | CONTRACTS.md Distribution requires byte-identical copies and a drift test in each consumer (it overrides the "no structural tests" rule) |
| In finding-v1 mode the hunter's `## Repro (finding-v1)` JSON list is the source: `finding_v1.py render` writes the draft's visible Steps from it, the repro-verifier re-runs the JSON steps (in order, each alone in its own Bash call from the copy's root), and `finding_v1.py write` writes the finding from the list the verifier reproduced | Parsing commands out of Steps markdown (rounds 1–4), then cross-checking hand-written Steps against the JSON (rounds 5–6) | Both kept breaking on free-form markdown; with one source nothing is matched or guessed (orchestrator decision D, msg_85e5274087c2) |
| `observed.rebuild` is the draft's `What happens` text | The raw step output | The raw output is already in `repro.steps[].stdout`; `What happens` states the wrong behaviour the verifier vouched for |
| An `--out` inside the target repo is refused | Allowing it | Constitution III and [drafts-location](../../../knowledge/decisions/drafts-location.md): hunting leaves nothing in the target |
| `--budget` is applied in `scope.py`, after the `--max` and `--live` cuts | Prose in `/hunt` only | Testable, and live runs can't skip it |
| `--yes` skips only the wait: the hunter count, cost and parts left out are still shown | Silent start | Constitution VI: cost is shown before starting |
| New `scripts/cost_log.py` appends one validated C7 line | The command writing JSON by hand | A malformed line would break `contracts.py cost` for the orchestrator |
| B6 applies to `/hunt` only | `/audit` too | The spec's B6 names `/hunt`'s hunters; asked the orchestrator as a follow-up |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** spec §Backlog 1 (vendor contracts): Given the vendored `contracts/v1`, when `contracts.py vendor-check contracts/v1` runs, then it prints `ok:` and exits 0.
- **AC-002** spec §B4: Given a verified draft with a `Severity: high` line and a `## Repro (finding-v1)` JSON list of steps, when `finding_v1.py write --repo R --out D --draft F` runs, then `D/BH-0001.json` passes `check_finding` with `class: build-defect`, `route: sdlc`, `criterion: null`, `observed.reference: "not run: no --reference"`, `verified_by.result: "reproduced"`, `repro: {"runner": "cli", "steps": <that list>}` and `draft` holding Steps rendered from that list; a live draft's repro carries `env: ["BASE", "BOB_AUTH"]`; with `BH-0009.json` already in `D`, the next is `BH-0010.json`.
- **AC-003** spec §B4: Given a draft with no `Severity:` line, no `## Repro (finding-v1)` section, a list that isn't one JSON list of exactly `{command, stdout}` strings, a command starting with `$ `, or an `--out` inside the repo, when `finding_v1.py write` or `render` runs, then it prints one `error:` line, changes and writes nothing and exits 1, without a traceback.
- **AC-008** spec §B4: Given a draft with a `## Repro (finding-v1)` list, when `finding_v1.py render --draft F` runs, then F's `## Steps to reproduce` is one fenced block of `$ command` lines each followed by its stdout, fenced longer than any backtick run in the output, which `drafts.py check` accepts; rendering again changes nothing.
- **AC-004** spec §B6: Given 5 parts and `--budget 450000`, when `scope.py` runs (and with `--live`), then 2 hunters are kept, the rest are in `skipped`, and `budget` reports `{"tokens": 450000, "per_hunter": 200000, "left_out": 3}`; a budget below 200000 prints one `error:` line and exits 1.
- **AC-005** spec §B6 / C7: Given `--cost-log F`, when `cost_log.py` is called for a hunter, then `F` gets one line that `contracts.py cost` accepts, with `tokens_in` and `tokens_out` null and `tokens_total` set; a second call appends a second line.
- **AC-006** spec §B6: Given a negative `--wall-s`, a non-number turn count or an unwritable file, when `cost_log.py` runs, then it prints one `error:` line, writes nothing and exits 1, without a traceback.
- **AC-007** spec §B4/§B6: `/hunt` takes `--format finding-v1 --out <dir>`, `--yes --budget <tokens>` and `--cost-log <file>` as described above, and default-mode drafts and `/hunt-post` are unchanged. `[manual: prompt text, checked in Review against the spec]`

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_contracts_vendor.py › test_vendored_contracts_match_manifest | `uv run pytest tests/test_contracts_vendor.py::test_vendored_contracts_match_manifest` |
| AC-002 | tests/test_finding_v1.py › test_verified_draft_becomes_a_c6_finding | `uv run pytest tests/test_finding_v1.py::test_verified_draft_becomes_a_c6_finding` |
| AC-003 | tests/test_finding_v1.py › test_refuses_without_severity_or_repro_or_outside_out | `uv run pytest tests/test_finding_v1.py::test_refuses_without_severity_or_repro_or_outside_out` |
| AC-008 | tests/test_finding_v1.py › test_render_writes_steps_from_the_json | `uv run pytest tests/test_finding_v1.py::test_render_writes_steps_from_the_json` |
| AC-004 | tests/test_scope.py › test_budget_caps_hunters_at_worst_case_cost | `uv run pytest tests/test_scope.py::test_budget_caps_hunters_at_worst_case_cost` |
| AC-005 | tests/test_cost_log.py › test_appends_valid_c7_lines | `uv run pytest tests/test_cost_log.py::test_appends_valid_c7_lines` |
| AC-006 | tests/test_cost_log.py › test_bad_input_writes_nothing | `uv run pytest tests/test_cost_log.py::test_bad_input_writes_nothing` |
| AC-007 | manual | prompt text: no test can run an agent; Review checks `commands/hunt.md` and `agents/bug-hunter.md` against the spec |

## Must never break

- Without `--format finding-v1`, `/hunt` writes the same drafts as 0.3.3 and `/hunt-post` files them unchanged.
- No finding is written unless its draft passed `drafts.py check` (with `--target` when live) and its verifier said `VERDICT: REPRODUCES`.
- Nothing is written inside the target repo.
- A finding file is never overwritten.

## Failure modes

- Untrusted input (drafts come from agents that read untrusted code): parsed as text only, never run → AC-002, AC-003
- I/O errors (missing or unwritable `--out` or `--cost-log`, non-UTF-8 draft) → AC-003, AC-006
- A huge or odd number in an existing file name in `--out` → AC-002 (bounded parse)

## Out of scope

- `--oracle` (part 2), `--reference` and HTTP replay repros (part 3), browser mode (part 4), departures (part 5).
- `--yes --budget` for `/audit`.
- Shell state shared between finding-v1 steps (a `cd`, `export` or variable carried from one step to the next): known limit; each step stands alone (the one-shell runner was dropped after review round 9, by the user's decision).
- Changing the cost preview's units (fresh tokens); the preview notes the B0 multiplier instead.
- A version bump or release tag: the release runbook has no pre-release step.

## Review

- **Recommended and chosen:** code, default depth (built-in `code-review`, medium), because Public Surface isn't `- none`; chosen by the trigger list (low risk, not asked). Every round past 2 was run on the orchestrator's (and, for rounds 9–10, the user's) typed decision.
- **Verdicts:** `.sdlc/.work/findings/2026-11-08-m-finding-v1-budget/code-reviewer-r1.md` … `r10.md`: r1–r10 FAIL; round 10 waived after its two findings were fixed (see Drift).
- **Fixed:** r1 F1–F7 (heredoc, inline code, indented and adjacent fences, case-insensitive names hang), r2–r4 (step parser edge cases, leading to the strict form, then decision A's JSON switch), r5–r6 (substring and layout matching of JSON against Steps, leading to decision D: the JSON is the only source and `render` writes Steps from it), r7 R7-1–R7-8 (verifier runs JSON instead of Steps, header-only `Severity:`/`Set before running:`, two Steps sections refused, CR-aware fence), r8–r9 (one-shell runner added, then removed by the user's decision), r10 R10-2/R10-3 (live `export` and no-copy `cd` in the step instructions). Each script fix started with a failing test in `tests/test_finding_v1.py`.
- **Tickets:** `_sections` duplicates `drafts.py`'s section parser (shared helper); the refusal test is one table-driven test of 12 cases; which verdict a step relying on earlier shell state gets; shared shell state between steps (known limit, Out of scope); `_quoted`/`shlex.quote` left with the runner; `--yes --budget` for `/audit`; the vendored `contracts.py` CLI prints `→`, which fails on a Windows console without UTF-8 (`PYTHONIOENCODING=utf-8` needed).
- **Drift and manual checks:** Deviations: the vendored files and exports (exact MANIFEST copy); module exports behind the CLIs; the C6 repro is bug-hunter's own `cli` shape (user's choice (a)); the JSON repro switch, decision D, AC-008/AC-009 added and AC-009 removed, AC-004 wording fixed; AC-008's red recorded after the fact by hiding `render` for one run; `waived round 10` (two prompt edits committed unreviewed, as directed). Tests: `uv run pytest` 173 passed, 17 failed, all 17 the Windows rows in `.sdlc/baseline.md` (diffed). AC-007 (manual): `commands/hunt.md`, `agents/bug-hunter.md` and `agents/repro-verifier.md` checked against spec §B4/§B6 by each review round; default-mode text and `/hunt-post` unchanged.
- **Lessons filed:** [recurring-defects.md](../recurring-defects.md) (structured repro data, not parsed markdown).
