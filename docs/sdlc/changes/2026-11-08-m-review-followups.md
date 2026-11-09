# bug-hunter 0.4: part 2 and part 3 review follow-ups

## Why

**Request (verbatim):** from the orchestrator (Orca, msg_34addfc88592): "Answers: R2-3 -> flaky (C6 class, routed to orchestrator; never drop a reproduced finding silently). R2-7 -> refuse --reference on the same scheme+host+port as --target (two servers must be two origins; avoids the shared masking key). S-5 -> yes, add the host/login scan on observed and draft in write, passing the target names. Part-2 findings from the mis-targeted review: fix the two likely-real ones test-first (oracle.py --live must keep only HTTP-serving parts and exit 1 when none, like scope.py; oracle.py must skip symlinks like scope.py), triage the other 23 as tickets in one list. Do these first, on a branch stacked on 1296515, then part 4."

These close the open questions from part 3 ([2026-11-08-m-reference-classify.md](2026-11-08-m-reference-classify.md), Review) and two defects in part 2's `oracle.py` ([2026-11-08-m-oracle-scoping.md](2026-11-08-m-oracle-scoping.md)). The orchestrator's message settles each behaviour, so it stands as the plan's approval.

## Decisions

| Decision | Ruled out | Why |
|---|---|---|
| A rebuild whose fresh replay passes is `flaky` (route orchestrator), not "not a finding" | Dropping it | Only verified drafts reach `write`, so a pass now means the runs disagree (orchestrator R2-3) |
| `_place` compares scheme, host (loopback names as one) and port; the base path no longer counts | Allowing two base paths on one origin | Two servers must be two origins, and masking keys addresses by origin (R2-7) |
| `write`/`classify` take `--target <name>` and `--ref-target <name>` (with `--repo`), and refuse a finding whose `observed` or `draft` names either target's host or holds one of its logins | A new flag pair named after `--reference` | `--reference` already names the reference's result file; the check reuses `drafts.py`'s leak rules, without its `Set before running:` rule |
| `oracle.py scope --live` keeps only parts whose files define HTTP routes (`scope.SERVES_HTTP`), renumbers them, and exits 1 with one `error:` line when none do | Tagging every part `live-http` | Same rule as `scope.py --live` |
| `oracle.py` reads no spec or repo file through a symlink (the file or a folder under the spec or repo root) | Following it | Same rule as `scope.py`; a link could bring a file from outside into agent prompts |
| The other 23 part 2 findings go to `docs/sdlc/todo.md` as one list | Fixing them now | Orchestrator: triage as tickets |

**Proposals not asked for:** None.

## Acceptance criteria

- **AC-001** orchestrator R2-3: Given a rebuild result `pass` from the fresh replay (with any reference result), when `classify` runs, then the class is `flaky`, routed to the orchestrator.
- **AC-002** orchestrator R2-7: Given `--target` and `--reference` on the same scheme, host and port with different base paths, when `live_proxy.py` runs, then it prints one `error:` line and exits 1.
- **AC-003** orchestrator S-5: Given `write --repo R --target uat --ref-target ref` and fresh results whose message names the reference's host or holds one of its logins, when it runs, then it writes nothing and prints one `error:` line naming the problem but not the value; clean results are written as before.
- **AC-004** part 2 finding 1: Given a spec whose features have one part that defines HTTP routes and one that doesn't, when `oracle.py scope --live` runs, then only the route part is kept (renumbered, with `live-http`); with no route part, it prints one `error:` line and exits 1.
- **AC-005** part 2 finding 5: Given a story, `domain.md` or `openapi.json` that is a symlink, when `oracle.py scope` runs, then its text is not read (story `null`, no rules or operations from it).

## Acceptance tests

| AC | Test | Run |
|---|---|---|
| AC-001 | tests/test_reference.py › test_classification_table_every_row | `uv run pytest tests/test_reference.py::test_classification_table_every_row` |
| AC-002 | tests/test_reference.py › test_reference_flags_are_checked | `uv run pytest tests/test_reference.py::test_reference_flags_are_checked` |
| AC-003 | tests/test_reference.py › test_write_refuses_target_hosts_and_logins | `uv run pytest tests/test_reference.py::test_write_refuses_target_hosts_and_logins` |
| AC-004 | tests/test_oracle.py › test_live_keeps_only_parts_serving_http | `uv run pytest tests/test_oracle.py::test_live_keeps_only_parts_serving_http` |
| AC-005 | tests/test_oracle.py › test_spec_files_are_not_read_through_symlinks | `uv run pytest tests/test_oracle.py::test_spec_files_are_not_read_through_symlinks` |

## Must never break

- Without `--target`/`--ref-target`, `write` and `classify` behave as on part 3; without `--live`, `oracle.py scope` output is unchanged.
- No error line echoes a secret: a leak is named by the kind of value and the account, never the value.

## Failure modes

- Untrusted input (result files, spec files, the hunted repo's tree): JSON and text only; links not followed → AC-003, AC-005

## Out of scope

- The 23 other part 2 findings (ticketed in `docs/sdlc/todo.md`); part 4 (B3), which follows on its own branch.

## Review

- **What fired:** a security review and a code review. Both fire because `Risk: high` (a secret-leak scan on findings, and untrusted spec files and links) and `## Public Surface` isn't `- none`. The orchestrator's directives imply both.
  - security ran on `sdlc:code-reviewer` (opus) with the brief's security section;
  - code ran on the built-in `code-review` (`high --max-findings all`);
  - every round past 2 ran on the orchestrator's typed decision.
- **Verdicts.** Every report is in `.sdlc/.work/findings/2026-11-08-m-review-followups/`.
  - Security:
    - r1 FAIL (S-1, the lock read through a symlink);
    - r2 FAIL (R2-1, the host match opened by the r1 fix F1);
    - r3 FAIL (R3-1, plain host names);
    - r4 FAIL (R4-1, JSON letter escapes);
    - r5, a focused probe by reading, FAIL (R5-1 to R5-3);
    - r6, a scripted probe of 6,762 leaking, 124 clean and 20 login cases, PASS.
  - Code:
    - r1 FAIL (F1, a plain host name refused every finding);
    - r2 FAIL (R2, a portless plain host no longer checked);
    - r3 FAIL (C3-1, the loopback port prefix);
    - r4 PASS.
  - Orchestrator decisions: msg_cd655d4876a7 (A, after round 2), msg_b40cfc890430 (A), msg_71e20506382d (B), msg_c8371a5d0521 (A).
- **High findings and their fixes.** Each fix started with a failing test, in `tests/test_reference.py` or `tests/test_oracle.py`.
  - S-1: the lock, a folder in between, a junction and the spec folder itself are now checked for links (`_linked`).
  - F1, R2-1, R2, R3-1, C3-1, R4-1 and R5-1 to R5-3 are one class: matching a target's host in text an agent or target wrote. The final structure:
    - `_spellings` decodes JSON, `\x`, HTML and percent escapes, strips ANSI codes, and repeats until nothing changes (bounded);
    - `_host_patterns` has no left boundary. A dotted host, IPv4 or IPv6 is a substring match with a right boundary only after a digit. A plain name counts only after `scheme://` (with any `user@`) or as `name:port`. A loopback target is any alias with its port.
    - The host-shape × encoding table pins all of this.
- **Medium and low bugs, fixed the same way:**
  - logins in every masked form, on every spelling (S-2, F2);
  - `--live` lists dropped features and swaps a left-out route file in before lines, stacks and edge inputs are computed (F3, F4, R3, C3-6, C3-8);
  - error wording: `write` tells a target's echo from the draft's own text (F7, F8, C3-7, R4-3);
  - the spec-folder guard normalises its path (R4, C3-5);
  - `hunt.md` wording (R6, C3-10, C4-4, C4-5, C4-9).
- **Tickets.** All in `docs/sdlc/todo.md`:
  - the leak-scan known limits: a protocol-relative `//plainname` without a scheme; loopback aliases (kept by decision); `localhost:80`; prefixes cut by the 500-character cap; rare address spellings; upper-cased escapes; scan cost on huge drafts; two sources of truth with the masker;
  - S-4 to S-7, F11 and F12, C3-11, C3-14 and C4-10/C4-11;
  - the 23 part 2 findings.
- **Drift and manual checks:**
  - Deviations:
    - `drafts.leaks` exported;
    - the leak flags on `write` only;
    - one deviation line per round (r1 to r6) describing its fixes.
  - Tests: `uv run pytest` gives 216 passed and 17 failed. All 17 are the Windows rows in `.sdlc/baseline.md` (diffed). AC-001 to AC-005 failed first, then passed.
- **Lessons filed:** [recurring-defects.md](../recurring-defects.md) gets two lines: boundary checks on partly decoded text, and an encoding table that varies one character class.
