---
description: Hunt reproducible bugs in this repo and write a verified issue draft for each. Shows the cost and waits for your go first; never posts anything.
argument-hint: [paths…] [--max N]
---

# /hunt

Take the repo in the current directory to a folder of ready-to-file drafts. Every draft's repro was run by a hunter and re-run by a separate verifier from the draft alone. You never edit the target repo, and you never post anything: the owner files drafts with `/hunt-post`.

`$ARGUMENTS` holds optional repo-relative paths and `--max N`. `$PLUGIN` below means `${CLAUDE_PLUGIN_ROOT}`.

## 1. Scope and cost

1. `REPO=$(git rev-parse --show-toplevel)`; not a git repo → say so and stop.
2. Run `python3 "$PLUGIN/scripts/scope.py" "$REPO" <paths…> [--max N]`. A non-zero exit → show its message and stop. Its JSON has `parts` (each `id`, `dir`, `files`), `skipped`, `hunters` and `est_tokens`.
3. `DRAFTS=$(python3 "$PLUGIN/scripts/drafts.py" dir "$REPO")`, then `python3 "$PLUGIN/scripts/known.py" "$REPO" "$DRAFTS"`: the known list, given to every hunter.
4. Pick the edge-input lists for each part: `$PLUGIN/edge-inputs/generic.md` always, plus `$PLUGIN/edge-inputs/python-cli.md` when the part has `.py` files. No list yet for other kinds of code: say that those parts get the generic list only.

## 2. Ask before spending

Show the owner, in a few lines:

- `hunters` hunters on these parts (dir and file count each), and about `est_tokens` tokens, plus about 20k per verifier (one per finding);
- the parts left out by `--max` (`skipped`), and that raising `--max` or passing paths changes that;
- whether open issues could be listed (the known list says when they couldn't, so duplicates can't be ruled out);
- that hunters and verifiers run this repo's code in throwaway copies under a temp dir, so only go ahead on a repo you trust (container isolation isn't supported yet).

Then ask: "Start N hunters?" Wait for the owner's yes. Anything else → stop, having run nothing.

## 3. Hunt

1. `SCRATCH=$(mktemp -d)`: outside the repo. Each agent gets its own subfolder.
2. Dispatch one agent per part, all at once, with `subagent_type: bug-hunter:bug-hunter`. Its prompt: `REPO`, its part's files, `SCRATCH=$SCRATCH/hunter-<id>`, the paths of its edge-input lists, and the known list. Nothing else.
3. From each reply, take each `=== DRAFT === … === END ===` block and the DROPPED lines. Drop a draft whose root cause (file and function) matches another draft's or an item on the known list, keeping the clearer one.
4. Write each draft to `$SCRATCH/drafts/<part>-<n>.md` and run `python3 "$PLUGIN/scripts/drafts.py" check` on it. A draft that fails is dropped with the problems it printed; don't rewrite a hunter's steps or output.

## 4. Verify

Dispatch one agent per remaining draft, all at once, with `subagent_type: bug-hunter:repro-verifier`. Its prompt: the draft's text, `REPO`, and `SCRATCH=$SCRATCH/verifier-<part>-<n>`. Never the hunter's reasoning or anything else from its reply. Keep only drafts whose verifier's last line is `VERDICT: REPRODUCES`; the rest are dropped with that line.

## 5. Write the drafts

For each kept draft: `mkdir -p "$DRAFTS"`, `NN=$(python3 "$PLUGIN/scripts/drafts.py" next "$DRAFTS")`, copy it to `$DRAFTS/$NN.md`, and run `drafts.py check` on the copy. Then `rm -rf "$SCRATCH"`.

## 6. Report

- A table: number · title · root-cause file, with the path to `$DRAFTS`.
- Dropped: one line each (couldn't reproduce, verifier verdict, known, format), so the owner sees what was left out.
- Next: `/hunt-post <numbers> --label <label>` files the ones the owner picks.
