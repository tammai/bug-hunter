---
type: run
title: "B0 run 7: /hunt lib --max 1 rerun on python-markdown2"
description: Rerun after the fence fix; the traceback draft now survives, but it carried the owner's home path (defect 6).
---

# B0 run 7: `/hunt lib --max 1` rerun on python-markdown2

- **Target:** as in [run 1](2026-11-08-b0-1-python-markdown2.md); the 3 drafts from run 1 were on the known list.
- **bug-hunter:** branch `2026-11-08-m-b0-live-validation` @ `f770d1b` (CommonMark fence reading in use), headless child with every `ORCA_*` variable unset.
- **Date:** 2026-11-08. Model: claude-opus-5-5.

## Cost

| Step | USD | Input | Output | Cache read | Cache write |
|---|---|---|---|---|---|
| Preview | 0.05 | 4 | 538 | 87,736 | 2,416 |
| Hunt + verify + drafts | 2.48 | 89,276 | 40,214 | 2,573,567 | 147,614 |
| **Total** | **2.53** | | | | |

Agents: 1 hunter (19.0k output, 1.84M cache read, 05:06:22–05:11:46), 3 verifiers in parallel (1.1k–1.9k output each, 05:12:40–05:13:11). This hunter's processed tokens are far above the preview's "about 100k per hunter".

## Result

Kept (all `VERDICT: REPRODUCES`): 04 wavedrom checks only the first fenced block's language; 05 `-x toc` crashes on a document with no headings (the bug run 1 lost to the fence defect: its traceback now passes `drafts.py check`); 06 a bare `&` in image alt text isn't escaped.

Dropped by the hunter: 2 known (#43 family, #179), 5 not clearly bugs, 2 couldn't reproduce (`latex2mathml` not installed; locale-dependent encoding).

## bug-hunter defects found

- **Defect 6:** draft 05's traceback holds `C:\Users\<owner>\AppData\Local\Temp\…`, the owner's account name, in a draft meant for a public issue. It passed `drafts.py check`, and `/hunt` may not rewrite it. Fixed in `2ef6a7f`: `drafts.py check` rejects a draft containing the checking user's home folder in any of its forms. A rescan of every B0 draft flags only this one.

Run verdict: **not clean**. The fence fix (defect 4) worked as intended.
