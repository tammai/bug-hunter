---
type: run
title: "B0 run 1: /hunt lib --max 1 on python-markdown2"
description: First live /hunt (Python CLI); 3 drafts kept, 1 proven bug lost to a drafts.py fence bug.
---

# B0 run 1: `/hunt lib --max 1` on python-markdown2

- **Target:** https://github.com/trentm/python-markdown2 @ `0ea342a56bf43f96e0c045da63e550cef7083f3f`, part `lib` (`lib/markdown2.py`), edge inputs `generic`, `python-cli`. No installs (no lockfile).
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `a9b15a9`, loaded with `claude -p --plugin-dir <bug-hunter>` from the target root (headless; `--permission-mode auto --permission-prompts none`), resumed with `yes` after the preview.
- **Date:** 2026-11-08. Model: claude-opus-5-5 (session and all agents).

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview (scope, known list, cost question) | 0.25 | 4 | 565 | 61,284 | 28,770 |
| Hunt + verify + drafts | 1.52 | 36,626 | 23,840 | 968,687 | 112,245 |
| **Total** | **1.78** | | | | |

Agents (from their transcripts): 1 hunter (7.7k output, 325k cache read, 04:40:20–04:42:26), 3 verifiers in parallel (1.3k–2.1k output each, 04:43:07–04:43:32). The preview's "about 100k tokens per hunter" is close to fresh tokens (input + output + cache write ≈ 46k for the hunter) but far below processed tokens (≈ 370k with cache reads).

## Result

Kept (each re-run by a separate verifier, `VERDICT: REPRODUCES`), in `~/.bug-hunter/github.com/trentm/python-markdown2/drafts/`:

1. `--output` with several inputs keeps only the last file's HTML (`main`, 5065–5067).
2. `main(argv)` ignores `argv` and parses `sys.argv` (`main`, 4994).
3. `toc_html` malformed when a later heading is shallower than the first (`calculate_toc_html`, 4644–4651).

Dropped:

- **`-x toc` crashes on a document without headings**: proven by the hunter, but dropped by `drafts.py check` (`missing section: ## Expected`, `## Root cause`). **bug-hunter defect** (Defect 4 in the change file): the pasted Python 3.11+ traceback has an indented `~~~~^^^^` caret line that the check read as a code fence. Fixed test first; the hunter's exact draft now passes `drafts.py check`.
- `--output` / `--link-patterns-file` without an encoding: couldn't reproduce (UTF-8 default on this Python).
- `--compare` with spaces in paths: couldn't reproduce (needs Perl and `Markdown.pl`).
- Tables, wiki-tables, CRLF metadata, duplicate TOC headings: probed, correct.

## bug-hunter defects found

- Defect 4: fence reading in `drafts.py` / `findings.py` (above).
- Found before the run, in its preview: Defect 2 (plain `--max 1` picked `setup.py` over `lib/`), worked around with the `lib` path and fixed in `a9b15a9`.

Run verdict: **not clean** (a bug-hunter defect cost a proven bug).
