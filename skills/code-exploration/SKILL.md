---
name: code-exploration
description: Find out what is in an unfamiliar Python codebase and how it fits together, using `api-inventory` (every public name with its signature and summary) and `pyan3` (call graphs and module dependency graphs). Use when orienting in a subsystem you have not read, before writing a helper that may already exist, when answering "what calls this function?" or "how does F end up calling G?", when you need an adjacency list of who-calls-what to reason about code, or when a picture of a source tree's shape would answer faster than a dozen greps.
---

# Exploring a codebase

Two tools, answering different halves of "what is going on in here". Pick by the question:

| The question | The tool |
|---|---|
| What exists here? Does a helper for this already exist? | `api-inventory` — public names, signatures, summaries |
| How does it connect? What depends on what? | `pyan3 --module-level` or `--depth 0` |
| What calls this function? | `pyan3 --function F --direction up` |
| How does F end up calling G? | `pyan3 --paths-from F --paths-to G` |
| Why is an edge I expected missing? | It may have been culled — see *Edges the graph deliberately omits* |
| I don't know what to ask yet | Render the graph and look at it |

**Start coarse.** A module-level pass is usually what tells you which question is worth asking; then
drill in. Reaching for full detail first gives you a graph too big to read and no question to read
it for.

# What exists: `api-inventory`

Prints every `__all__` entry of a package — name, signature, first line of the docstring — grouped
by module. It answers the question grep cannot: grep needs the *name*, which is the one thing you do
not have when you are looking for a helper someone else named.

```
api-inventory raven/raven/common/          # a package, with summaries
api-inventory --names-only raven/raven/    # a whole project, names only
api-inventory --width 78 pkg/mod.py        # one file, narrower summaries
```

**It parses source by default and imports nothing**, which is what makes it safe on packages with
heavy or side-effecting imports. Two flags change that:

- `--import` — import and introspect instead. Needed when `__all__` is computed in a way a static
  read cannot follow; the report says which modules those are, rather than under-reporting silently.
Macro-using packages need no flag and no preparation: `--import` reads the target's source first
and enables `mcpyrate` when it finds a macro- or dialect-import. Bytecode for the run goes to its
own cache directory, so the answer does not depend on what compiled the package earlier, and the
package itself is never written to. See the `macro-enabled-python` skill for the expander.

An inventory that could not import everything **exits 2** and names what it skipped. Check the
status when scripting against it: the missing names look exactly like names that do not exist.

Test directories and the `00_stuff` / `00_old` scratch areas are skipped (`--include-tests` keeps
tests). Both modes agree on the same package, which the test suite checks.

# How it connects: call graphs with `pyan3`

`pyan3` statically analyzes Python source and emits a call graph (who
defines / calls / uses what), or with `--module-level` a module dependency
graph. Useful for understanding code structure, visual/structural testing, and
exploration.

## Choose the output format by the question and the reader

Both forms are readable by both audiences, so neither is ever ruled out. Two things vary:
the kind of question each form answers, and who is going to look at the result. A human
gets more out of a picture, especially one they can zoom and search; the agent gets more
out of `--text`, which is greppable and quotable — except when the question is about
*shape*, where an image wins for either reader.

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

  **Scope the graph before handing it over.** The viewer is a DPG app in pure Python, so
  it does not tolerate very large graphs — give it a full analysis of Raven at once and
  the GUI grinds to a halt. Cut the graph down first with `--depth`, `-x`, or
  `--namespace`, and hand over a region rather than a fleet.

  You cannot drive the viewer yourself — it's a GUI app. Rasterize a PNG for your own
  eyes (graphviz does both layout *and* rasterization there); launch the viewer for
  theirs.

The two are usually one workflow rather than a choice. A coarse pass — `--module-level`
or `--depth 0`, in either format — is often what tells you which question is worth
asking; then drill into that region with `--function`, `--direction up`, or
`--paths-from`/`--paths-to`. Reaching for full detail on the first pass gives you a graph
too big to read and no question to read it for.

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

Pick by the question: "who actually depends on this at runtime?" is the call graph; "what does this module pull in?" is module-level. (An import that's never used appears in *both* — the call graph records a uses edge for the import statement itself, and keeps it precisely because nothing finer does.)

**Needs pyan3 ≥ 2.8.1 to be trusted on a package-structured project.** Before that, `--module-level` silently dropped every dependency on a *package* rather than on one of its modules, in both directions, so the graph read clean while missing real edges. If `pyan3 --version` reports anything older, `pipx upgrade pyan3`. The call graph, `--depth 0` included, was never affected.

## Edges the graph deliberately omits (pyan3 ≥ 2.8)

`pyan3` draws less than it knows, so a missing edge is not automatically something it failed to
resolve. Two rules to know before concluding that it did:

- **A module's uses edge is dropped when a finer edge already carries it.** `import b` produces a
  uses edge whether or not the name is ever referenced, so a module node accumulates one per
  imported name — each running parallel to the edges of the functions that actually use it. Those
  go. Nothing disappears at module scale: the finer edge collapses back onto the same pair under
  `--depth 0`, and an import nothing else records is kept. Defines edges are never touched.

  **`--keep-subsumed-edges` turns it off** (`cull_subsumed_edges=False` from the API), and that is
  what you want when the question is *about imports* — "does this module import `b` at all?" reads
  the raw edge set, not the culled one.

- **Under `--grouped` / `--nested-groups`, every module is a box**, with its own node inside it
  labelled `<module>` — CPython's name for the module-level code object. So a box holding only
  `<module>` is a module with no members, and a box with no `<module>` is one whose body neither
  uses anything nor is used. A module's defines edges into its own box are not drawn either.

The rules in full, with worked examples, are in pyan's README under *What the graph leaves out*.

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
- `--ignore-parameter-annotations` — since 2.8, a parameter's annotation is treated as its type, so `def f(obj: Thing): obj.method()` draws an edge to `Thing.method`. Only classes and modules bind; a string annotation, `Optional[X]` or a union resolves to nothing. It's a static reading, and the value that actually arrives may be an overriding subclass — turn it off where a codebase's annotations are loose enough that base-class edges mislead more than they help.
