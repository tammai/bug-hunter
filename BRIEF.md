# bug-hunter: brief

A Claude Code plugin that hunts bugs in any repo and writes an issue draft for each. A bug is only reported once its repro has been run and checked. The plugin never posts anything itself: a person decides what is filed.

## Where it comes from

On 2026-11-05 this recipe found 12 bugs in tammai/sdlc, and each was reproduced against `main`. Ten became the tohe phase 1 gate issues, sdlc#14 and #16–#24. #14 was fixed by tohe and merged as sdlc PR #15. The recipe was a few hand-run subagent prompts. This plugin packages it.

## The recipe

1. **Scope.** Map the repo and split it into parts of a few files each, one hunter per part. Pay most attention to code with clear inputs and outputs: CLIs, parsers, libraries, scripts.
2. **Hunt.** Each hunter reads its part closely and tries the edge inputs on the list for that kind of code:
   - paths with spaces, non-ASCII or Windows separators;
   - CRLF line endings, trailing spaces, empty files and sections;
   - markdown variants, such as bold or code in table cells;
   - digits inside words (`OAuth2`), off-by-one, `B10` sorting before `B2`;
   - missing or null keys in JSON on stdin;
   - subprocess failures, encodings, running a step twice, stray files such as `.DS_Store`.
3. **Prove.** A finding counts only with the exact command that was run and its actual wrong output. Hunters work in throwaway copies or temp dirs, never edit the target repo, and drop anything they can't reproduce.
4. **Skip what's known.** Hunters are told about open issues and earlier findings, so nothing is filed twice.
5. **Verify.** A separate verifier agent re-runs each repro from the report alone, without the hunter's reasoning.
6. **Draft.** Each confirmed bug becomes `drafts/NN.md` in a fixed format:
   - What happens
   - Steps to reproduce, with the actual output
   - Expected
   - Root cause, with file, function and lines
7. **The owner posts.** A post step files only the drafts the owner picks, from the owner's own `gh` login, with a label they choose. With the label `bug` on a repo tohe manages, tohe picks the issue up and fixes it.

## Rules a bug must meet

- A real defect: wrong output, a crash, data loss or wrong state. Not style, a feature request or a design opinion.
- Small: fixable in one or two files, with a test.
- Proven: the repro ran and its output is in the draft.

## Parts, as a first guess

| Part | Role |
|---|---|
| `/hunt [paths] [--max N]` | Command: maps the repo, starts the hunters (capped at N), runs the verifier, writes the drafts |
| `bug-hunter` agent | Hunts one part. Read-only on the repo; runs code only in a scratch dir |
| `repro-verifier` agent | Re-runs one repro and says whether it reproduces |
| Edge-input lists | One per kind of code: Python CLI, Go, Node, web |
| `/hunt-post <numbers>` or `post.sh` | Files the chosen drafts with `gh issue create` |

## Risks

- **Running untrusted code.** Hunters run the target repo's code. On a repo the owner doesn't trust, run it in a throwaway copy or a container.
- **Cost.** Each hunter spent about 100k tokens. Cap the number of hunters per run and say the expected cost before starting.
- **Fit.** It suits code with clear inputs and outputs. It is weak on UIs and on code that needs a running service; there it should say it couldn't reproduce a bug, not guess.
- **Scope of what it finds.** It finds edge-case bugs, not design flaws or problems that only show under load.
