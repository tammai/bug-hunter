# /audit counts only the submodules inside the run's paths as gaps

## Why

Request (docs/sdlc/todo.md, `/audit` verdict follow-ups round 2, R3-L3): "every submodule is a gap, even one outside the run's scope".

Proof: `tests/test_audit_scope.py › test_only_submodules_inside_the_runs_paths_are_a_gap` adds submodules at `api/vendor/lib` and `web/vendor/lib`; `scope.py <repo> api --focus security` still lists both under `coverage.submodules`, so a run limited to `api` is kept from Safe by a submodule it never covered.

Root cause: `_coverage` lists every submodule entry in the index without applying the run's `paths`, unlike its other coverage facts.

## Decisions

- With `paths`, a submodule is listed when it lies under one of them, or when a path lies inside it (the run asked about part of the submodule). Ruled out: dropping submodules from a scoped run altogether, which would hide one inside the scoped folder.

## Acceptance criteria

- AC-001: a run limited to `api` lists `api/vendor/lib` and not `web/vendor/lib`; a run with no paths lists both.

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_audit_scope.py › test_only_submodules_inside_the_runs_paths_are_a_gap | `uv run pytest tests/test_audit_scope.py -k test_only_submodules_inside_the_runs_paths_are_a_gap` |

## Must never break

- `test_submodules_are_a_gap_and_their_filters_never_run`: an unscoped run still lists every submodule, and no submodule's filter runs.

## Out of scope

- Single-branch clones, and the other round 2 follow-ups.

## Review

No review ran: no trigger fired.
