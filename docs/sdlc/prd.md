# bug-hunter: product requirements

<!-- Written by /sdlc:setup from the interview, approved by the user. Yours from then on: sdlc never overwrites it,
     and eject keeps it. Define reads it as background when a change touches product scope. -->

## Problem

Hand-run bug-hunting prompts found 12 real bugs in tammai/sdlc on 2026-11-05, each reproduced against `main`. But the recipe lives in ad-hoc subagent prompts: it is hard to rerun, its scope and cost aren't controlled, and nothing stops an unproven or duplicate bug from being reported. bug-hunter packages the recipe as a Claude Code plugin.

## Users and audience

Developers and maintainers who own a repo and want its edge-case bugs found and written up before users hit them. First user: the author, on tammai/sdlc and the repos tohe manages.

## Goals and non-goals

**Goals**
- Every reported bug has a repro that a separate verifier re-ran from the report alone.
- One command takes a repo to a folder of ready-to-file drafts.
- No duplicates of open issues or earlier findings.
- The expected cost is shown before a run, with a cap on the number of hunters.
- `/hunt --target` hunts a running local dev server or UAT the owner allowed, through a proxy that holds the test logins and a request budget; never production.
- Before deploy, a security and PII audit (`/audit`) reports authorization, injection, secrets, session and personal-data problems, each with evidence a second agent failed to disprove, plus a PII inventory, in a private report.

**Non-goals**
- Posting or filing anything the owner didn't pick, and posting audit findings at all.
- Fixing bugs (tohe does that).
- Reporting style issues, feature requests, design flaws or problems that only show under load (security and PII problems are covered by `/audit`).
- Editing the target repo.

## Core capabilities

1. `/hunt [paths] [--max N]`: map the repo, run hunters up to the cap, verify, write `drafts/NN.md` (What happens · Steps to reproduce with actual output · Expected · Root cause with file, function and lines).
2. `bug-hunter` agent: hunts one part, read-only on the repo, running code only in a scratch dir, guided by an edge-input list per kind of code.
3. `repro-verifier` agent: re-runs one repro and says whether it reproduces.
4. Skip what's known: hunters are given open issues and earlier findings.
5. `/hunt-post <numbers>`: files the chosen drafts with the owner's own `gh` login and a label they choose.
6. `/audit [paths] [--max N]`: secrets scan, npm/composer dependency audit, one `security-auditor` per part and one `finding-verifier` per finding; numbered findings and `REPORT.md` with a PII inventory in `~/.bug-hunter/<host>/<owner>/<repo>/audit/`. Optional owner `policy.md` says who may see what.

## Constraints

- Ships as a Claude Code plugin.
- Scripts in Python 3.12, standard library only.
- Hunters run target code only in throwaway copies or temp dirs; on an untrusted repo, in a container.
- About 100k tokens per hunter.
- Posting needs a logged-in `gh`.
- A bug counts only if it is a real defect (wrong output, crash, data loss, wrong state), fixable in one or two files with a test, and its repro ran with the output in the draft.

## Success measures

- At least 90% of drafts reproduce when the owner re-runs them.
- Zero drafts duplicate an open issue.
- A `/hunt` run on sdlc's pre-fix commit finds most of the 12 known bugs.

## Open questions

- Container isolation for untrusted repos: later (decided 2026-11-05).
- Edge-input lists: generic, Python CLI, Node/Vue, Go, Rust, JVM, Ruby and PHP shipped (2026-11-06).
