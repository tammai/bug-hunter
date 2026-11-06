---
paths:
  - "commands/**/*"
  - "agents/**/*"
  - "edge-inputs/**/*"
  - "security/**/*"
  - ".claude-plugin/**/*"
---

# Plugin prompt rules

<!-- Tier 2: loads when touching the plugin's commands, agents and edge-input lists. Detail lives in knowledge/ and the constitution. -->

- Hunters and verifiers never edit the target repo; they run its code only in a scratch copy or temp dir. A live hunt (`/hunt --target`) reaches a running server only through `live_proxy.py`, and agents never get the target URL or its tokens — why: [constitution III](../../docs/sdlc/constitution.md)
- A bug draft is kept only with the exact command and its actual output, re-run by `repro-verifier` from the draft alone; an audit finding only at a proof level (proven, traced, advisory) that `finding-verifier` failed to disprove from the finding alone — why: [constitution I](../../docs/sdlc/constitution.md)
- Nothing posts to GitHub except the owner-run post step, on drafts the owner names; audit findings are never posted — why: [constitution II](../../docs/sdlc/constitution.md)
- No prompt output carries a secret's value or a person's data: write `<redacted>` — why: [constitution, Audit Bar](../../docs/sdlc/constitution.md)
- `/hunt` states hunter count and expected token cost before starting and honours `--max`.
- Drafts keep the fixed four sections: What happens · Steps to reproduce · Expected · Root cause.
- Agent prompts get only what they need (their part, known issues), not the hunter's reasoning for the verifier.
