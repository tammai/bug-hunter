---
paths:
  - "commands/**/*"
  - "agents/**/*"
  - "edge-inputs/**/*"
  - ".claude-plugin/**/*"
---

# Plugin prompt rules

<!-- Tier 2: loads when touching the plugin's commands, agents and edge-input lists. Detail lives in knowledge/ and the constitution. -->

- Hunters and verifiers never edit the target repo; they run its code only in a scratch copy or temp dir — why: [constitution III](../../docs/sdlc/constitution.md)
- A finding is kept only with the exact command and its actual output, re-run by `repro-verifier` from the draft alone — why: [constitution I](../../docs/sdlc/constitution.md)
- Nothing posts to GitHub except the owner-run post step, on drafts the owner names — why: [constitution II](../../docs/sdlc/constitution.md)
- `/hunt` states hunter count and expected token cost before starting and honours `--max`.
- Drafts keep the fixed four sections: What happens · Steps to reproduce · Expected · Root cause.
- Agent prompts get only what they need (their part, known issues), not the hunter's reasoning for the verifier.
