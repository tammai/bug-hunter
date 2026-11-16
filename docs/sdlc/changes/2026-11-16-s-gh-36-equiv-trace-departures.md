# /hunt --oracle reads a departures registry with an equiv-trace rule

## Why

**Request (verbatim):** "Fix GitHub issue #36: contracts.py check_departures refuses match rule equiv-trace:<name>, which product-rebuild's equiv.py accept writes; accept it (non-empty name) in the departures check and make the oracle treat it as never matching an HTTP value."

**Proof:** `finding_v1.py classify --oracle <spec>` with a `departures.yaml` holding `match: [{runner: http, rule: "equiv-trace:invoices-total"}]` exits 1 with `error: departures.yaml: D-002 match 1: unknown rule equiv-trace:invoices-total (uuid, int, iso8601, same-as:<capture>, regex:<pattern>)`.

**Root cause:** vendored `contracts/v1/contracts.py` `check_departures` checks match rules against the HTTP replay step vocabulary (`_rule_problem`), which has no `equiv-trace:`.

## Decisions

- Fixed in the canonical contracts (product-rebuild 1.3.1, tammai/product-rebuild#11) and vendored here byte-identical; the drift test refuses a local edit. Ruled out: ignoring the error in `finding_v1.load_departures`, which would make bug-hunter's reading of C5 differ from the shared contract.
- No change to `matching_departure`: an `equiv-trace:` item has no pointer and `_rule_ok` returns False for it, so it never matches.

## Acceptance criteria

- **AC-001** Given a spec whose `departures.yaml` has an accepted `equiv-trace:<name>` entry before a matching `regex:` entry, when `finding_v1.py classify --oracle` runs, then it exits 0 and names the `regex:` entry, never the trace entry.
- **AC-002** Given `contracts/v1/` vendored at 1.3.1, then `vendor-check` passes and reports 1.3.1.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_departures.py › test_registry_with_an_equivalence_trace_is_read_and_never_matches | `uv run pytest tests/test_departures.py -k test_registry_with_an_equivalence_trace_is_read_and_never_matches` |
| AC-002 | tests/test_contracts_vendor.py › test_vendored_contracts_are_1_3_1 | `uv run pytest tests/test_contracts_vendor.py -k test_vendored_contracts_are_1_3_1` |

## Must never break

- An invalid or proposed departure still refuses or never matches, as `test_registry_is_read_and_checked` checks.

## Out of scope

- Re-vendoring 1.3.1 into rspec and sdlc.

## Review

No review ran: no trigger fired.
