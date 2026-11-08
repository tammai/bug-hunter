---
type: run
title: "Part 4 acceptance run: browser-mode /hunt on the fixture notes app"
description: Planted double-submit found in a real browser and reproduced by the verifier; $0.96 of an $8 cap.
---

# Part 4 acceptance run: `/hunt --target http://127.0.0.1:5177 --browser --max 1 --yes --budget 400000`

- **Target:** `tests/fixtures/browser-app`, copied into a throwaway git repo (no remote) and served with `PORT=5177 node server.js`; stopped after the run.
- **bug-hunter:** branch `2026-11-08-m-browser-mode` (uncommitted part 4 work on top of 5c0c8b9), loaded with `claude -p --plugin-dir <bug-hunter>` from the target root (`--permission-mode auto --permission-prompts none`), every `ORCA_*` variable unset, `--max-budget-usd 8`.
- **Machine:** Windows 11, Git Bash, node 24; Playwright browsers already installed (chromium and headless shell 1223, matching the fixture's locked `@playwright/test` 1.60.0).
- **Date:** 2026-11-08. Model: claude-opus-5-5. Approved by the orchestrator at a USD 8 cap (msg_af4092430112).

## Cost

| Step | USD | Input | Output | Cache read | Cache write | Turns | Wall |
|---|---|---|---|---|---|---|---|
| Hunt + verify + report | 0.96 | 20 | 6,819 | 508,084 | 44,135 | 10 | 4 min 15 s |

Agents: 1 hunter (about 24k tokens), 1 verifier (about 19k). Requests: 18 of 14,000 through the proxy (browser and curl); writes forwarded: 6 `POST /api/notes` (201), listed for clean-up.

## Result

One draft, `01`: "Double-clicking Save stores the same note twice".
- **The steps:** the locked install (`npm ci --ignore-scripts`), the `browser.py` fetch, a quoted heredoc writing `bh-repro.spec.ts`, and `python3 browser.py run --test bh-repro.spec.ts --base "$BASE"`.
- **What the browser showed:** `{"result": "fail", …, "Expected: 1\nReceived: 2"}`.
- **Verified:** the verifier re-ran the steps in a fresh copy and saw the same.
- **Dropped by the hunter:** a query string 404, a non-string note, and no body size limit.

**AC-010 met:** the planted double-submit bug was found in browser mode, and the verifier reproduced it.

## Caveats and bug-hunter notes

- **Hints in the fixture:** its comments name the planted defect ("the button stays enabled…"), and the hunter quoted them in Expected. The browser test proved the bug by itself, but a later run should use a fixture without these hints, so it measures finding rather than reading.
- **An unused account:** the draft's `Set before running:` line names `ACCEPT_ACCOUNT_BOB` although the test uses no account. It was copied from the prompt's example. The prompt should say to name only the accounts the test reads.
- **The fetch URL:** the `curl` step fetches `browser.py` from the `v0.3.3` tag, which doesn't have it until 0.4 is released (the stub server works the same way).
- **No open-issue list:** the repo had no git remote, so issues couldn't be listed (expected for a throwaway repo).

Run verdict: **acceptance met**. The two notes above are prompt and fixture tickets, not defects in the browser path.
