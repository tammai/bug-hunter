# The /audit report explains a pre-id secret kept open by a same-shape sibling

## Why

Request (docs/sdlc/todo.md, `/audit` verdict follow-ups round 2, L-A and L-1): "the report should explain a pre-id finding kept open by a same-shape sibling, and tell the owner to close it with a `rotated` line once the key is rotated".

Proof: `tests/test_findings.py › test_the_report_explains_a_pre_id_secret_kept_open_by_a_same_shape_sibling`. A secrets finding written before ids existed, re-checked against two same-shape secrets in its file, neither at its line, stays open, and nothing in the recheck JSON or the report says why or how to close it.

Root cause: `_recheck` puts the unpairable finding in `still_open` with every other open finding, so the report can't tell it apart.

## Decisions

- `recheck` lists such findings in a new `unpaired` list (they stay in `still_open`), and the report adds one note per finding: a same-shape secret is still in its file, which one it was can't be told, and `- NN rotated: <note>` in `accepted.md` closes it once the key is rotated. A note, not a gap: the finding is open and counts as before. Ruled out: guessing a pairing, which the earlier review rejected.

## Acceptance criteria

- AC-001: a pre-id secret finding that can't be paired is listed in `recheck`'s `unpaired` and the report names it with the `rotated` line to close it; a paired one isn't.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_findings.py › test_the_report_explains_a_pre_id_secret_kept_open_by_a_same_shape_sibling | `uv run pytest tests/test_findings.py -k test_the_report_explains_a_pre_id_secret_kept_open_by_a_same_shape_sibling` |

## Must never break

- Pairing, verdicts and which findings stay open are unchanged; no report line carries a secret.

## Out of scope

- The other round 2 follow-ups.

## Review

No review ran: no trigger fired.
