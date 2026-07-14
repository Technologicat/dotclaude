---
name: callgraph
description: Generate a static call graph or module-level dependency graph for Python source with pyan3. Use when mapping how functions or modules connect, understanding the structure/wiring of an unfamiliar codebase, exploring a Python source tree's shape, doing visual or structural testing, answering "what calls this function?" or "how does F end up calling G?" (via `--function --direction up` and `--paths-from`/`--paths-to`), or when you (the agent) need an adjacency list of who-calls-what to reason about code. Produces `--text` for direct agent reading, or a `--dot` graph for visual viewing.
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

  The viewer runs the layout engine itself (no precompute needed), and the
  `raven-xdot-viewer` shell function activates Raven's venv on its own — nothing
  to set up first. **Must background** (`&`).

  Report the **pyan3** command you ran, and any warnings it emitted. (The graph is
  only as good as what pyan could resolve statically; the warnings say what it
  couldn't.)

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
