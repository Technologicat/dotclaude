---
name: callgraph
description: Generate a static call graph or module-level dependency graph for Python source with pyan3. Use when mapping how functions or modules connect, understanding the structure/wiring of an unfamiliar codebase, exploring a Python source tree's shape, doing visual or structural testing, answering "what calls this function?" or "how does F end up calling G?" (via `--function --direction up` and `--paths-from`/`--paths-to`), or when you (the agent) need an adjacency list of who-calls-what to reason about code. Produces `--text` for direct agent reading, or a `--dot` graph for visual viewing.
---

# Call graphs with pyan3

`pyan3` statically analyzes Python source and emits a call graph (who
defines / calls / uses what), or with `--module-level` a module dependency
graph. Useful for understanding code structure, visual/structural testing, and
exploration.

## Choose the output format by the question, not by the reader

Both forms are readable by both audiences. What differs is the kind of question each one answers.

- **You have a specific question** — does F call G? what calls F? how does F reach G?
  — use `--text`. It's an adjacency list: precise, greppable, and it answers the
  question you asked. This holds whoever is asking; a human chasing one call path
  wants text too, not a picture.

  ```
  pyan3 <paths> --text
  pyan3 --module-level <paths> --text      # module dependency graph
  ```

- **You don't yet know what to ask** — render the graph. Layout *is* information:
  clusters, hubs, unexpected edges and lopsided coupling are visible at a glance and
  essentially invisible in an adjacency list. Worth it for a lateral look at an
  unfamiliar codebase; not for a question you could have grepped.

  Two ways to render, depending on who's looking:

  **You (the agent) can look at the graph yourself** — rasterize with graphviz and read
  the image:

  ```
  pyan3 <paths> --dot --colored --grouped --nested-groups --concentrate --file /tmp/pyan3_callgraph.dot
  dot -Tpng /tmp/pyan3_callgraph.dot -o /tmp/pyan3_callgraph.png
  ```

  ...then read `/tmp/pyan3_callgraph.png`. This works and is often the fastest way to
  get a feel for an unfamiliar module's shape.

  **For the user to explore interactively**, hand them the viewer instead — it has
  search, zoom, and pan, so they can go from overview to specifics without regenerating
  anything:

  ```
  raven-xdot-viewer /tmp/pyan3_callgraph.dot &
  ```

  Hand it the `.dot` — it runs graphviz's *layout* pass itself to get an `.xdot`
  (skipping that step if you hand it an `.xdot` already), and then draws with its own
  DPG-based xdot renderer. Graphviz's rasterizer is not involved: interactive rendering
  is Raven's, which is what makes zoom and pan stay sharp. So don't pre-render a PNG
  for the user — that would flatten the graph they want to explore.

  The `raven-xdot-viewer` shell function activates Raven's venv on its own, so there's
  nothing to set up first. **Must background** (`&`).

  You cannot drive the viewer yourself — it's a GUI app. Rasterize a PNG for your own
  eyes (graphviz does both layout *and* rasterization there); launch the viewer for
  theirs.

Report the **pyan3** command you ran, and any warnings it emitted — for either output
format. (The graph is only as good as what pyan could resolve statically; the warnings
say what it couldn't.)

## Targets

`<paths>` is one or more files or glob patterns:

- `pkg/subpkg/*.py` — a single package
- `pkg/**/*.py` — an entire project (globstar)
- `pkg/app.py` — a single file
- `--module-level pkg/` — module dependency graph (recursive)

## `--depth 0` vs `--module-level` — different questions

They both give you a module-scale picture, and they are not the same graph:

- **`--depth 0`** collapses the *call graph* to module nodes. An edge means *code in A calls or uses something in B*.
- **`--module-level`** analyses *imports*. An edge means *A imports B* — whether or not anything is called.

So an import that's never used shows up in `--module-level` and not in `--depth 0`. Pick by the question: "who actually depends on this at runtime?" is the call graph; "what does this module pull in?" is module-level.

## Flags worth knowing

`pyan3 --help` is the full list; these are the ones that change what you can answer.

**Scoping the graph** — a whole-project call graph is usually too big to read:

- `--depth N` — collapse to at most N nesting levels. `0` = modules only, `1` = modules + classes/top-level functions, `2` = + methods, `max` = full detail (default).
- `-x PATTERN`, `--exclude PATTERN` — repeatable. Basename match without a path separator, full-path match with one. Quote it: `--exclude 'test_*.py' --exclude '*/tests/*'`.
- `--namespace NS` / `--function F` — filter to one region.
- `--direction {up,down,both}` — with `--function`/`--namespace`: `down` = callees only, `up` = callers only. **This is how you answer "what calls this?"** without reading the whole graph.

**Answering specific questions:**

- `--paths-from F --paths-to G` — list the call paths between two functions (`--max-paths`, default 100). Use when the question is "*how* does F end up calling G?" rather than "what does the code look like".
- `-a`, `--annotated` — annotate nodes with module and source line number. Turns the graph into something you can navigate back into the source from.
- `-n`, `--no-defines` — uses-only graph (drop the "defines" edges, keep the calls).

**Correctness gotchas:**

- `--root ROOT` — package root. Inferred by default, but inference **cannot** detect a PEP 420 namespace package (no `__init__.py` at the package directory), and will silently produce wrong module names. If the top-level package is a namespace package, pass `--root` explicitly.
- `--namespace-constructor FQN` — register a constructor whose kwargs become attribute bindings, so `config.attr` resolves through it. Built in: `unpythonic.env.env`, `types.SimpleNamespace`, `argparse.Namespace`. Add your own (repeatable, or comma-separated) when a project passes config objects around and the graph comes out missing those edges.

Pick `--text` vs `--dot` by who's going to read the result.
