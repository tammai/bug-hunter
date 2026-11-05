<!--
Sync report
- Version: none → 1.0.0 (first ratification)
- Principles added: I. Proof Before Report, II. The Owner Posts, III. Hands Off the Target,
  IV. Test-First Scripts, V. Simplicity (sdlc default), VI. Bounded Cost
- Sections added: Bug Bar, Development Workflow, Governance
- Follow-ups: none (no CLAUDE.md yet; nothing contradicts)
-->
# bug-hunter Constitution

## Core Principles

### I. Proof Before Report (NON-NEGOTIABLE)
A finding MUST NOT become a draft unless its exact command was run and its actual wrong output is captured in the draft. A separate verifier MUST re-run every repro from the draft alone before it is kept. A finding that doesn't reproduce MUST be dropped or labelled "couldn't reproduce", never guessed.
Rationale: the plugin's whole value is that every bug it reports is real.

### II. The Owner Posts
The plugin MUST NOT create issues, comments or PRs on its own. Posting MUST file only the drafts the owner names, from the owner's own `gh` login, with the label they choose.
Rationale: a person decides what is filed in their repo.

### III. Hands Off the Target
Hunters and verifiers MUST NOT edit the target repo. Target code MUST run only in a throwaway copy or temp dir (a container for repos the owner doesn't trust). Scratch files MUST stay in the scratch dir, never in the target.
Rationale: hunting must leave no trace and do no harm.

### IV. Test-First Scripts
Every change to `scripts/` MUST start with a failing pytest that covers the behaviour, including the edge inputs bug-hunter itself hunts for (spaces and non-ASCII in paths, CRLF, empty files, missing JSON keys, subprocess failure). Scripts MUST use only the Python 3.12 standard library.
Rationale: a bug finder with edge-case bugs undermines itself, and adding no dependencies keeps it installable anywhere.

### V. Simplicity
Changes MUST be the smallest that meet the acceptance criteria. New abstractions, options, configuration, public exports and dependencies MUST be justified by a current requirement, not a possible future one; an abstraction with a single implementation needs a written reason. Comments MUST explain *why*, never restate the code or its change history; doc comments are for exported API and are one line unless the contract needs more.

### VI. Bounded Cost
`/hunt` MUST show the expected hunter count and token cost before starting, and MUST respect `--max`. New agent prompts SHOULD state what they read and stop at their part.
Rationale: about 100k tokens per hunter adds up quickly.

## Bug Bar

A draft MUST describe a real defect (wrong output, crash, data loss, wrong state) that can be fixed in one or two files with a test. Style, feature requests, design opinions and load-only problems are out. Drafts MUST use the fixed format: What happens · Steps to reproduce (with actual output) · Expected · Root cause (file, function, lines).

## Development Workflow

Changes go through sdlc (define → build → review → ship). CI runs `uv run ruff check .` and `uv run pytest`, and both MUST pass to merge.

## Governance

This constitution overrides other practice in this repo. Amendments go through `sdlc:project-constitution` with a version bump and a sync report. Reviews check changes against the MUSTs above.

**Version**: 1.0.0 | **Ratified**: 2026-11-05 | **Last Amended**: 2026-11-05
