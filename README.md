# bug-hunter

A Claude Code plugin that hunts reproducible edge-case bugs in a repo and writes an issue draft for each. A bug is kept only when its repro was run by a hunter and re-run by a separate verifier from the draft alone. It never posts anything: you pick what gets filed.

> **Status:** v0.1.0, not yet released. The scripts are tested, but there hasn't been a live `/hunt` run yet, so start with `--max 1`. Installing it by name (`/plugin install`) isn't set up yet; load it from a clone (below).

## Install

You need Python 3.12 or newer and `git`. `/hunt-post` and the open-issues check also need `gh`, logged in.

```
git clone https://github.com/tammai/bug-hunter.git
cd /path/to/the/repo/you/want/hunted
claude --plugin-dir /path/to/bug-hunter
```

The repo is private for now, so cloning needs access to it.

## Hunt

From the root of the repo you want hunted:

```
/hunt [paths…] [--max N]
```

1. **Scope.** It splits the repo's tracked source files into parts of up to 5 files from one folder, leaving out tests and non-code files. Paths limit it to those folders or files.
2. **Ask.** It shows the hunter count, the expected cost (about 100k tokens per hunter, plus about 20k per verifier) and the parts `--max` leaves out. Then it waits for your yes. Answer no and nothing runs.
3. **Hunt.** One `bug-hunter` agent per part reads the code and tries edge inputs: paths with spaces, CRLF, empty files, `B10` sorting before `B2`, missing JSON keys, failing subprocesses and more. It drops anything it can't reproduce and anything already known (open issues and earlier drafts).
4. **Verify.** A separate `repro-verifier` re-runs each draft's steps in a fresh copy, from the draft alone. Only drafts that reproduce are kept.
5. **Draft.** The report lists the kept drafts, and what was dropped and why.

If `/hunt` isn't found, use `/bug-hunter:hunt` (and `/bug-hunter:hunt-post`).

### Drafts

Drafts are written outside the repo:

- `~/.bug-hunter/<host>/<owner>/<repo>/drafts/NN.md`;
- `~/.bug-hunter/local/<folder>/drafts/NN.md` for a repo without an `origin`.

Each draft has the same four sections:

- **What happens**
- **Steps to reproduce**, with the actual output
- **Expected**
- **Root cause**: file, function and lines

To check a draft by hand: `python3 scripts/drafts.py check <draft>`.

### What it finds, and what it doesn't

It finds real defects (wrong output, a crash, data loss, wrong state) that can be fixed in one or two files with a test. It doesn't report style, feature requests, design opinions, or problems that only show under load. It works best on code with clear inputs and outputs: CLIs, parsers, libraries and scripts. Edge-input lists exist for any code (`edge-inputs/generic.md`) and for Python CLIs (`edge-inputs/python-cli.md`); Go, Node and web come later.

## File the ones you want

Read the drafts first: `/hunt-post` shows only titles before it files. Then, from the same repo:

```
/hunt-post 1 3 --label bug
```

It files only the drafts you name, from your own `gh` login, with the label you choose. It refuses before filing anything when:

- a draft is missing or fails the format check;
- two drafts share a number;
- `gh` isn't logged in.

Each filed draft is recorded in `posted.json` next to the drafts, so it's never filed twice. If filing stops part way, the drafts already filed stay recorded.

## Safety

Hunting runs the target repo's code on your machine. Run it only on repos you trust: container isolation isn't supported yet.

What it does to contain that:

- **Never changes the repo.** Agents have no edit tools and read the repo only. Code runs in a throwaway clone made by `scripts/throwaway.py`. The clone has the tracked files and their uncommitted changes, but no `origin` remote and no `.venv` or other untracked environments. It's refused when a symlink points outside it. Worktrees are handled.
- **Keeps your logins out of reach.** Every agent command runs without your `gh` token or config, your global git config and credential helpers, or your SSH agent. Agents never run `gh`.
- **Treats what it reads as data.** Repo files, issue titles (anyone can write them) and drafts are never taken as instructions.
- **Posts nothing on its own.** Only `/hunt-post` files, and only the drafts you name.

## Develop

```
uv sync --frozen
uv run pytest
uv run ruff check .
```

| Folder | What's in it |
|---|---|
| `commands/` | `/hunt` and `/hunt-post` |
| `agents/` | `bug-hunter` and `repro-verifier` |
| `edge-inputs/` | the edge-input lists hunters work through |
| `scripts/` | standard-library Python the commands call: `scope.py`, `known.py`, `drafts.py`, `post.py`, `throwaway.py` |
| `tests/` | pytest for the scripts, and checks on the prompt files |

Changes go through sdlc (`/sdlc:start`). Principles: [constitution](docs/sdlc/constitution.md). Background: [BRIEF.md](BRIEF.md) and the [PRD](docs/sdlc/prd.md). Releases: [release runbook](knowledge/runbooks/release.md).
