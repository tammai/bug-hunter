# Spec: bug-hunter 0.4.0, spec oracle, reference comparison, browser mode

2026-11-08 · @Tam Mai · draft for sign-off · depends on contracts v1 ([01](01-shared-contracts.md))

## Problem

bug-hunter 0.3.1 has the right verification model (a hunter proves each bug by running it; a separate verifier re-runs it from the draft alone), but for a rebuild it judges against the wrong oracle and misses most of a web app:

1. **Oracle.** A hunter confirms "from the code and its docs that the output is wrong". In a rebuild the code's own docs were written by the builder; the oracle must be the spec and the reference.
2. **No reference comparison.** A crash that the reference also has is a reference defect, not a build defect; a behaviour that differs but is listed as a departure is not a bug. bug-hunter cannot tell these apart.
3. **No UI.** Anything that needs a browser is dropped as "couldn't reproduce".
4. **Output.** Issue drafts for GitHub; the pipeline needs classified, routable findings.
5. **Unproven.** The README says no live `/hunt` run has happened yet.

## Decisions

| Question | Decision |
|---|---|
| Live validation first | No 0.4 feature work starts before part B0 is done; its fixes ship as 0.3.x. |
| Mode trigger | Flags only (`--oracle`, `--reference`, `--format finding-v1`). Without them 0.4 behaves exactly as 0.3. |
| Reference access | Through the same `live_proxy.py`, with two named targets. Agents never see either URL or any token. |
| Browser | Playwright, only from the repo's own locked dev dependencies (installed by the existing locked-install rules). Repo without Playwright → browser mode unavailable, reported. No `npx` fetch. |

## Requirements

### B0 Live validation (ships as 0.3.x)

Run `/hunt --max 1` on three repos of different stacks (one Python CLI, one Node/TS service, one Go module), then `/hunt --target http://localhost:<port> --max 1` on one HTTP service, then `/audit` once. Fix every defect found in bug-hunter itself, test first. Record each run (cost, kept, dropped and why) in `knowledge/runs/`. Exit: three consecutive runs with no bug-hunter defect.

### B1 `--oracle <spec>`

`<spec>` is a folder with `criteria.lock.json` (rspec spec or an sdlc spec-backed repo).

- **Scope by feature, not by folder.** Parts become features in scope: for each, the story file, `domain.md` rules it cites, its contract operations, and the source files that implement it (from the sdlc change files' `## Tasks` file lists for those criteria; fallback: `git log --name-only` of commits naming the feature's change file). Cap 8 source files per part.
- **Expected comes from the spec.** A draft's `Expected` section cites a criterion ID or a `domain.md` rule. A wrong behaviour no criterion or rule covers is kept as a `spec-gap` candidate, not a bug.
- **Risk ranking** picks which parts run under `--max`: criteria at level < 2 first, then most changed lines, then most failure modes. The ranking and the parts left out are shown before the cost question.
- The edge-input lists still apply; the oracle changes the judgement, not the search.

### B2 `--reference <target>`

Requires `--target`. Both are names in `targets.json` (localhost allowed as today). The proxy serves two bases; agents use `$BASE` (rebuild) and `$REF_BASE` (reference).

- The hunter runs every repro against both before drafting.
- `repro-verifier` re-runs it against both, from the draft alone.
- Classification, applied by script from the two results (`findings.py classify`), not by the agent:

| Rebuild | Reference | Spec covers it | Class |
|---|---|---|---|
| wrong | correct | — | `build-defect` |
| wrong | same wrong | yes, spec says otherwise | `build-defect` (reference defect not to copy; propose a departure) |
| wrong | same wrong | no | `reference-defect` |
| differs | — | matches a `departures.yaml` entry | `accepted-departure` (dropped, listed) |
| correct per reference | — | spec says otherwise | `spec-gap` |

- Writes are allowed on the reference only when its target has `"writes": true` (local reference).

### B3 Browser mode

- Enabled when the rebuild repo's locked dev dependencies include `@playwright/test` and a browser is installed for it; `scope.py` reports why when not.
- Hunters and verifiers write repros as a single Playwright test file that reads `BASE`/`REF_BASE` and account headers from the environment, run with the repo's locked `playwright test` command inside the throwaway copy.
- The proxy rules (budget, no redirects to other hosts, write gating) apply to browser traffic: the browser is launched with the proxy as its only allowed origin.
- `edge-inputs/web-ui.md`: double submit, back/forward after a write, stale tab, two tabs editing one record, long and RTL text, empty and huge lists, slow network, session expiry mid-form, keyboard-only flows.

### B4 `--format finding-v1 --out <dir>`

Writes contracts C6 files instead of drafts: `repro` in C4 runner format, `observed.rebuild` and `observed.reference`, `class` from B2 (or `build-defect` / `spec-gap` candidate from B1 without a reference), `verified_by` from the verifier. Drafts and `/hunt-post` are unchanged for the default format.

### B5 Departures

With `--oracle`, `departures.yaml` beside the lock is read; matching behaviour is dropped with the departure ID in the report. A hunter may propose a departure in a finding; it never writes the registry.

### B6 Orchestrated runs

`--yes --budget <tokens>` skips the interactive cost question when an orchestrator has pre-approved a budget; the run stops starting new hunters when the estimate reaches it and reports the parts not run. Each agent run appends to `cost.jsonl` (C7) when `--cost-log <file>` is given.

## Backlog parts

0. B0 (0.3.x releases).
1. Vendor contracts; B4 output; B6 flags.
2. B1 feature scoping, oracle briefs, risk ranking.
3. B2 two-target proxy, dual repro, `classify`.
4. B3 browser mode and `web-ui.md`.
5. B5.

## Acceptance

- Existing tests pass unchanged; default-mode `/hunt` output is byte-identical in structure to 0.3.
- Unit tests: classification table (every row), feature scoping fallback, risk ranking order, proxy two-target isolation (an agent cannot reach `REF_BASE` through `BASE` or vice versa), `finding-v1` validation through `contracts.py`.
- Fixture: rebuild + reference pair (two small HTTP apps in `tests/fixtures/`) with one planted build defect, one shared reference defect, one departure, one spec gap → each classified correctly in one `--oracle --reference` run.
- One browser-mode run on a fixture app finds a planted double-submit bug and the verifier reproduces it.
