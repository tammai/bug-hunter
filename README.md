# bug-hunter

A Claude Code plugin that hunts reproducible edge-case bugs in a repo and writes an issue draft for each. A bug is kept only when its repro was run by a hunter and re-run by a separate verifier from the draft alone. It never posts anything: you pick what gets filed.

## Use

From the root of the repo you want hunted:

```
/hunt [paths…] [--max N]
```

It splits the repo's source files into parts of up to 5 files, shows how many hunters that is and the expected cost (about 100k tokens each), and waits for your yes. Hunters and verifiers run the repo's code only in throwaway copies in a temp dir and never change the repo, so run it only on repos you trust (container isolation isn't supported yet).

Drafts land in `~/.bug-hunter/<owner>-<repo>/drafts/NN.md`, outside the repo, each with the same four sections: What happens · Steps to reproduce (with the actual output) · Expected · Root cause (file, function, lines). Later runs skip them, and the repo's open issues.

To file the ones you want, from the same repo, with your own `gh` login:

```
/hunt-post 1 3 --label bug
```

It files only those drafts, records each in `posted.json`, and never files one twice.

## Install

```
claude --plugin-dir /path/to/bug-hunter
```

Needs Python 3.12 and `git`; `/hunt-post` and the open-issues check need a logged-in `gh`.

## Develop

```
uv sync --frozen
uv run pytest
uv run ruff check .
```

Scripts are standard-library Python in `scripts/`; the commands are in `commands/`, the agents in `agents/`, and the edge-input lists in `edge-inputs/`.
