---
name: callgraph
description: Generate a static call graph or module-level dependency graph for Python source with pyan3. Use when mapping how functions or modules connect, understanding the structure/wiring of an unfamiliar codebase, exploring a Python source tree's shape, doing visual or structural testing, or when you (the agent) need an adjacency list of who-calls-what to reason about code. Produces `--text` for direct agent reading, or a `--dot` graph for visual viewing.
---

# Call graphs with pyan3

`pyan3` statically analyzes Python source and emits a call graph (who
defines / calls / uses what), or with `--module-level` a module dependency
graph. Useful for understanding code structure, visual/structural testing, and
exploration.

## Choose the output format by audience

- **For your own understanding** (you, the agent, reading the wiring) — use
  `--text`. It produces a human-readable adjacency list you can read directly,
  no viewer needed.

  ```
  pyan3 <paths> --text
  pyan3 --module-level <paths> --text      # module dependency graph
  ```

- **For the user to view visually** — render to dot and open the viewer:

  ```
  pyan3 <paths> --dot --colored --grouped --nested-groups --concentrate --file /tmp/pyan3_callgraph.dot
  raven-xdot-viewer /tmp/pyan3_callgraph.dot &
  ```

  The viewer runs the layout engine itself (no precompute needed).
  `raven-xdot-viewer` requires Raven's venv to be active. Report the command
  used and any warnings.

## Targets and flags

`<paths>` is one or more files or glob patterns, plus any extra pyan3 flags
appended after the paths:

- `raven/common/gui/xdotwidget/*.py` — a single package
- `raven/**/*.py` — an entire project (globstar)
- `raven/visualizer/app.py` — a single file
- `--module-level raven/` — module dependency graph (recursive)
- `raven/librarian/*.py --no-defines` — uses-only graph
- `raven/librarian/*.py --depth 1` — collapse to modules + top-level

See `pyan3 --help` for the full flag set. The target normally comes from the
user's request; pick `--text` vs `--dot` by who's going to read the result.
