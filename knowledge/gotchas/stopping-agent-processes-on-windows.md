---
type: gotcha
title: Stopping the processes agents start, on Windows (Git Bash)
description: Why agents' background servers are listed by the isolation prefix and stopped with reap.py, not kill.
---

# Stopping the processes agents start, on Windows (Git Bash)

Found in B0's live runs (2026-11-08, [runs](../runs/)); each trap below left a target's server running or wrote into the target repo before it was fixed.

- **`$!` is an MSYS PID, not a Windows PID** (62812 vs 21856 in one check). `taskkill` can't use it; only Git Bash's own `kill` can. `scripts/reap.py` calls `kill` on Windows and `os.kill` elsewhere.
- **`cmd && prog &` backgrounds a subshell.** `$!` is the subshell; killing it leaves `prog` running under PID 1, where nothing finds it again. `reap.py --record`, run by the isolation prefix's `EXIT` trap, writes each job's whole tree to `bg.pids` while the subshell lives; agents `exec` the program after a setup command and stop processes with `reap.py`, never `kill`.
- **Agents forget.** A prompt rule ("list every PID") was followed in one run and not the next. The listing happens in `isolate.py`'s output, which every agent call already `eval`s.
- **`cd copy && … & echo $! > f`** puts the `cd` in the background job; `f` lands in the folder the shell started in, which for an agent is the target repo. The isolation prefix now starts each call inside the agent's copy.
- **Windows' command lookup tries the current folder first** unless `NoDefaultCurrentDirectoryInExePath` is set. Claude Code's shell sets it, which hides the problem; other hosts don't. `reap.py` sets it and refuses a `ps`/`kill` found in the current folder.
- **Tests that start background shells:** call Git's `bash` by its resolved path (a bare `bash` finds WSL's in System32), and remember `os.environ` keys are uppercase on Windows.
- **Open:** a PID in `bg.pids` can be reused by an unrelated process before `reap.py` runs (ticket S4).
