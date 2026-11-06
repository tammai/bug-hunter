<!--
Sync report
- Version: 1.0.0 → 1.1.0 (MINOR: guidance materially expanded for audit findings; nothing removed)
- Principles changed: I. Proof Before Report (audit findings: proof levels and an independent
  attempt to disprove), II. The Owner Posts (audit findings are never filed), VI. Bounded Cost
  (covers /audit; auditors may read beyond their part to follow a trace)
- Sections added: Audit Bar
- Follow-ups: .claude/rules/plugin-prompts.md says a finding is kept "only with the exact command
  and its actual output"; that now holds for bug drafts only. Update it to point at Principle I.
-->
# bug-hunter Constitution

## Core Principles

### I. Proof Before Report (NON-NEGOTIABLE)
A finding MUST NOT become a bug draft unless its exact command was run and its actual wrong output is captured in the draft. A separate verifier MUST re-run every repro from the draft alone before it is kept. A finding that doesn't reproduce MUST be dropped or labelled "couldn't reproduce", never guessed.

An audit finding (`/audit`) MUST carry evidence at one of three proof levels: **proven** (a repro run in a throwaway copy, or a script's output, captured in the finding), **traced** (a source-to-sink path, every hop cited as `path:line` with the code quoted), or **advisory** (a dependency advisory record). An agent's audit finding MUST be kept only if a separate verifier, given the finding alone, tried to disprove it, searching the whole repo for a control that covers it, and could not. Anything else MUST be dropped and listed as not confirmed, never reported as a finding.
Rationale: the plugin's whole value is that everything it reports is real; a security finding that can't be run is still held to evidence a second reader checked.

### II. The Owner Posts
The plugin MUST NOT create issues, comments or PRs on its own. Posting MUST file only the drafts the owner names, from the owner's own `gh` login, with the label they choose. Audit findings MUST NOT be filed or posted at all; they stay in the owner's private audit folder.
Rationale: a person decides what is filed in their repo, and a published vulnerability helps attackers before it helps anyone else.

### III. Hands Off the Target
Hunters and verifiers MUST NOT edit the target repo. Target code MUST run only in a throwaway copy or temp dir (a container for repos the owner doesn't trust). Scratch files MUST stay in the scratch dir, never in the target.
Rationale: hunting must leave no trace and do no harm.

### IV. Test-First Scripts
Every change to `scripts/` MUST start with a failing pytest that covers the behaviour, including the edge inputs bug-hunter itself hunts for (spaces and non-ASCII in paths, CRLF, empty files, missing JSON keys, subprocess failure). Scripts MUST use only the Python 3.12 standard library.
Rationale: a bug finder with edge-case bugs undermines itself, and adding no dependencies keeps it installable anywhere.

### V. Simplicity
Changes MUST be the smallest that meet the acceptance criteria. New abstractions, options, configuration, public exports and dependencies MUST be justified by a current requirement, not a possible future one; an abstraction with a single implementation needs a written reason. Comments MUST explain *why*, never restate the code or its change history; doc comments are for exported API and are one line unless the contract needs more.

### VI. Bounded Cost
`/hunt` and `/audit` MUST show the expected agent count and token cost before starting, and MUST respect `--max`. New agent prompts SHOULD state what they read and stop at their part; an auditor MAY read beyond its part to follow a trace but MUST report only on code its part reaches.
Rationale: about 100k tokens per hunter adds up quickly.

## Bug Bar

A draft MUST describe a real defect (wrong output, crash, data loss, wrong state) that can be fixed in one or two files with a test. Style, feature requests, design opinions and load-only problems are out. Drafts MUST use the fixed format: What happens · Steps to reproduce (with actual output) · Expected · Root cause (file, function, lines).

## Audit Bar

An audit finding MUST describe a security or personal-data problem with an impact: who can do what to whom, or what data goes where it shouldn't. Pattern matches without an impact are out. Findings MUST use the fixed format: title, Severity, Category, CWE, Proof, then Where (`path:line`) · Evidence · Impact · Fix. No output of the plugin MAY contain a secret's value or a person's data; values are written `<redacted>`.

## Development Workflow

Changes go through sdlc (define → build → review → ship). CI runs `uv run ruff check .` and `uv run pytest`, and both MUST pass to merge.

## Governance

This constitution overrides other practice in this repo. Amendments go through `sdlc:project-constitution` with a version bump and a sync report. Reviews check changes against the MUSTs above.

**Version**: 1.1.0 | **Ratified**: 2026-11-05 | **Last Amended**: 2026-11-06
