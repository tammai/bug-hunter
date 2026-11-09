# bug-hunter 0.4 part 5: departures registry

## Why

**Request (verbatim):** implement docs/specs/rebuild-upgrade/04-bug-hunter.md, part 5 only.

Part 5 is B5 of [docs/specs/rebuild-upgrade/04-bug-hunter.md](../../specs/rebuild-upgrade/04-bug-hunter.md): with `--oracle`, `departures.yaml` (contracts C5) beside the lock is read, a finding whose difference matches an accepted departure is classified `accepted-departure` (dropped, listed with the departure ID), and a hunter may propose a departure but never writes the registry. Part 3 left a stand-in `--departure <ID>` flag for this; it goes. Built on part 4 (branch `2026-11-08-m-browser-mode` @ 4b40a24).

**The user's words:** orchestrator brief (msg_340a75ba8c58) and answers (msg_6104f3b4442c, "All as proposed"):
- 04 Acceptance for this part: the fixture pair run classifies the departure-shaped difference as `accepted-departure` from `departures.yaml`.
- Q1 matching: an entry matches when it isn't `status: proposed`, a `match` item has `runner: http` and a `pointer`, the rebuild's replay failed at a JSON check on that pointer, and the rebuild's value there satisfies the item's rule (contracts' `_rule_ok`); the reference is not "same wrong". The value is read back from contracts' failure message; a cut message never matches (the safe side). Entries with no pointer, another runner, an empty `match`, or a playwright repro never match automatically (human-only, C5).
- Q2: `<spec>/departures.yaml`; missing → no departures; invalid per `contracts.check_departures` → one `error:` line, nothing written, and `/hunt` stops before the cost question; proposed entries → a warning, ignored for matching.
- Q3: remove `--departure`; editing part 3's unreleased tests is fine, noted as a deviation.
- Q4: several entries match → the first in file order.
- Q5: propose, never write: proposing stays row 2's script-set `propose_departure`; prompts say agents never write `departures.yaml`.
- Q6: M, risk low, code review with the 2-round cap.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| The rebuild's value is parsed from contracts' own failure message (`step N <ptr>: <json> does not satisfy rule …` or `step N <ptr>: got <json>, expected …`), with the pointer known from the entry and the failing step's `expect` | A new field in `replay`'s output | `replay`'s result shape is fixed and checked (`result_problem`); a cut message fails to parse and so never matches |
| A departure applies whenever the reference is not "same wrong", including a reference that didn't run | Only when the reference ran | Row 4's reference column is "—"; Q1(d). Closes part 3's ticket R2-9 |
| `/hunt` validates the registry with the vendored `contracts.py departures` | A new bug-hunter command | Contracts already has the check and its output lines (`error:`, `blocked:`) |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** spec §B5 / Q2: Given `--oracle <spec>`, when `finding_v1.py classify` or `write` runs, then `<spec>/departures.yaml` is read: a missing file means no departures; a file `contracts.check_departures` gives an error for (bad YAML, a missing `decided_by`, a bad ID) prints one `error:` line naming `departures.yaml` and writes nothing; a `status: proposed` entry is never matched.
- **AC-002** spec §B5 / Q1, Q4: Given the departures and an HTTP repro whose rebuild replay failed, when matching runs, then the first entry (file order) with an `http` match item whose pointer is the failing check's pointer and whose rule the rebuild's value satisfies is returned; a value that fails the rule, another pointer, a status failure, a cut message, an item with no pointer or another runner, an empty `match` or a playwright repro match nothing.
- **AC-003** spec §B2 row 4 with B5: Given a matched departure, when `classify` runs, then the class is `accepted-departure` (route `drop`, `departure: <ID>`) when the reference passed, failed differently or didn't run; when both failed the same way, rows 2, 3 and 5 apply as before.
- **AC-004** Q3: `finding_v1.py write` and `classify` no longer take `--departure`; passing it fails and writes nothing.
- **AC-005** spec §Acceptance (fixture): Given the fixture rebuild and reference apps behind the two-target proxy and the four planted drafts, when each is replayed against both and written with `--oracle`, then the departure-shaped difference is `accepted-departure` with `departure: D-001` from the fixture's `departures.yaml`, the others keep their classes (build defect, reference defect, spec gap), and `departures.yaml` is byte-identical afterwards.
- **AC-006** spec §B5: `/hunt --oracle` checks `departures.yaml` with `contracts.py departures` before the cost question (`error:` → stop; `blocked:` → shown as a warning), the report lists each `accepted-departure` finding as dropped with its departure ID, and hunter and verifier prompts say agents never write `departures.yaml`. `[manual: prompt text, checked in Review against the spec]`

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_departures.py › test_registry_is_read_and_checked | `uv run pytest tests/test_departures.py::test_registry_is_read_and_checked` |
| AC-002 | tests/test_departures.py › test_departure_matches_by_pointer_and_rule | `uv run pytest tests/test_departures.py::test_departure_matches_by_pointer_and_rule` |
| AC-003 | tests/test_departures.py › test_departure_applies_unless_the_reference_is_the_same_wrong | `uv run pytest tests/test_departures.py::test_departure_applies_unless_the_reference_is_the_same_wrong` |
| AC-004 | tests/test_departures.py › test_departure_flag_is_gone | `uv run pytest tests/test_departures.py::test_departure_flag_is_gone` |
| AC-005 | tests/test_reference.py › test_fixture_pair_is_classified | `uv run pytest tests/test_reference.py::test_fixture_pair_is_classified` |
| AC-006 | manual | prompt text: no test can run an agent; Review checks `commands/hunt.md`, `agents/bug-hunter.md` and `agents/repro-verifier.md` against spec §B5 |

## Must never break

- Without `--oracle`, `finding_v1.py` classifies as on part 4 (no departure is ever applied).
- `departures.yaml` is never written by bug-hunter or its agents.
- No finding is written unless its draft passed `drafts.py check` and its verifier said `VERDICT: REPRODUCES`; a finding file is never overwritten.
- `contracts.py vendor-check contracts/v1` prints `ok:` (contracts 1.1.1 unchanged).

## Failure modes

- Untrusted input (result files and the failure message carry a target's values): the value is parsed as JSON only, from a message whose pointer is known; anything unparsed doesn't match → AC-002.
- A broken or half-decided registry (owner's file): refused or ignored as C5 says → AC-001.

## Out of scope

- Departures for playwright, cli or maestro repros (human-only).
- A version bump, push or release tag; a live `/hunt` run.

## Review

- **Fired and chosen:** a code review, because `## Public Surface` isn't `- none` (`--departure` removed, `matching_departure` added). Risk is low and touches no `areas.sensitive`, so no security review ran (orchestrator Q6, msg_6104f3b4442c). It ran on the built-in `code-review` (`high --max-findings all`), under the orchestrator's 2-round cap.
- **Verdicts:** `code-reviewer-r1.md` FAIL (CR-2, CR-3, CR-5), then `code-reviewer-r2.md` PASS. Both are under `.sdlc/.work/findings/2026-11-08-m-departures/`. No finding was rated high.
- **Round 1 bugs, each fixed with a failing test first:**
  - CR-2: a departure on an early check could hide later checks and steps that never ran. A departure now matches only the repro's last check.
  - CR-3: a matched departure outranked a verified `Defect: yes`. Such a draft is now never dropped.
  - CR-5: the registry check ran on oracle hunts that never read it. It now runs only under Running reference.
  - Cleanups: CR-7 (no re-parse), CR-10 and CR-11 (tests trimmed to the testing rule), CR-12 (todo R2-9 removed, since this change closes it).
- **Round 2 bugs, fixed test first and closed by `verify.py`:**
  - R2-3: a message from an earlier check on the same pointer was read as the last check's failure.
  - R2-4: a `departures.yaml` reached through a link is now refused, as `oracle.py` does for other spec files.
  - Docs: R2-5 and R2-6 (`commands/hunt.md`), R2-7 (CHANGELOG), R2-8 (dead except clause), R2-9 (redundant test).
- **Orchestrator correction (msg_efa6fcb89650):** CR-1 was first rated a ticket, because its matching rule was the orchestrator's own Q1 decision. The orchestrator then tightened that rule, so it was fixed in this round, test first. An entry that lists `criteria` matches only a finding citing one of them; otherwise an entry that lists `features` matches only a finding whose criterion belongs to one of them; an entry with neither matches any finding. To stay in D-001's scope, the fixture's departure draft now also cites F-TSK-01.AC1.
- **Tickets:**
  - CR-4: matching parses contracts' failure wording; adds to S2-7. The fixture test uses real contracts output, so a rewording would fail it.
  - CR-6: `classify` and `write` print no warning for a skipped proposed entry; `/hunt` warns before the cost question.
  - CR-8: the failure message is parsed once per finding, which is acceptable.
  - CR-9: registry IDs have no upper digit bound.
  - R2-2: the comment was updated. Not a regression, since part 3 also applied a departure whenever the two results differed.
  - R2-10: the runner is inferred from the steps' shape.
  - R2-11: classify's departure rows sit in two tables.
  - R2-12: the registry test covers several cases.
- **Drift and manual checks:**
  - **Deviations** (each in the state file):
    - part 3's tests edited to drop `--departure` (Q3);
    - `load_departures` added and `with_reference`'s signature changed;
    - AC-002 narrowed (last check, scope);
    - AC-003 gains the `Defect: yes` exception;
    - the fixture draft's citation;
    - a linked registry is refused (that test skips where the OS account can't create symlinks: Windows here, so it was not seen failing locally);
    - CHANGELOG and todo updated.
  - **Tests:** `uv run pytest` gives 230 passed, 17 failed and 6 skipped. The 17 failures are exactly the Windows rows in `.sdlc/baseline.md` (diffed). AC-001 to AC-005 failed first, then passed.
  - **AC-006 (manual):** I checked `commands/hunt.md` (Running reference: Departures, Classify and Report bullets), `agents/bug-hunter.md` and `agents/repro-verifier.md` against spec §B5. The registry is checked before the cost question, `blocked:` is a warning, the report lists drops with their ID and summary, and agents never write `departures.yaml`. Both review rounds read the same text.
- **Lessons filed:** none new. The recurring "verified finding dropped by a script" defect from part 3 already covers CR-2 and CR-3.
