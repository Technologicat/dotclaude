---
name: macro-enabled-python
description: How to run, read, debug and reason about Python source that uses syntactic macros — `mcpyrate` (the expander) and `unpythonic.syntax` (the fleet's macro library). Use when a file carries `from ... import macros, ...` or `from ... import dialects, ...`; when something fails with "cannot import name 'macros'"; when macro changes appear not to take effect; when you need to see what a macro expands into (`step_expansion`, `stepr`, `show_bindings`); when reading quasiquoted macro code (`q`, `u`, `n`, `a`, `s`, `t`, `h`); or when tooling has to import, introspect, test or measure coverage on macro-using code.
---

# Macro-enabled Python

Two pieces, always together. **`mcpyrate`** is the macro expander — an import hook that rewrites the
AST at compile time. **`unpythonic.syntax`** is a library of macros built on it. Anything using the
latter needs the former active.

This is a map, not a manual: the authoritative documentation is `mcpyrate`'s `doc/` (`main.md`,
`quasiquotes.md`, `compiler.md`, `dialects.md`, `troubleshooting.md`) and `unpythonic`'s
`doc/macros.md`. Both projects' **unit tests are the edge-case documentation** — when a doc and your
reading of it disagree, the tests settle it.

For the pure-Python side of `unpythonic`, which the fleet uses far more, see the `unpythonic` skill.
For writing tests for macro-enabled code, see `testing-macro-enabled-python` — and note that this is
not a matter of preference: **pytest cannot run macro-enabled test modules at all**, because its
assertion-rewriting import hook cannot coexist with the expander's. That is why a separate test
framework exists rather than a pytest plugin.

## Recognizing it, and the hazard that follows

A module is macro-enabled if it carries either marker, both of the form
`from module import <marker>, name0, ...`:

- **`macros`** — binds macros for this module.
- **`dialects`** — enables a whole-module transformer (see `doc/dialects.md`).

Neither marker is a real name. Under regular Python the import raises
`ImportError: cannot import name 'macros' from ...`.

**The error is not the damage.** CPython writes the `.pyc` when it *compiles* a module, before the
failing body runs — so a plain-Python import leaves unexpanded bytecode behind, with an mtime saying
it is current. The next `macropython` run trusts that cache, skips expansion, and fails with the very
same ImportError, now under the tool that was supposed to fix it. Repair:

```
macropython -C <dir>          # clear bytecode caches; targets __pycache__ by name, touches nothing else
```

This is a hazard for **tooling** above all, which is what makes it easy to walk into: anything that
imports a package to introspect it — an inventory script, `pydoc`, autodoc, a REPL probe, plain
`pytest` collection — imports macro code without meaning to. Prefer reading source over importing
(`api-inventory` parses statically by default and refuses `--import` on a macro-using package unless
you pass `--macros`).

## Running it

```
macropython file.py           # run a macro-enabled main program
macropython -m some.module    # same, by module name
macropython -c 'code'         # macro-enabled `python -c`
macropython -i                # macro-enabled REPL (-pi for pylab mode)
macropython -C <dir>          # clean bytecode caches
```

For a program that is mostly ordinary Python with a macro-using module somewhere inside, plain
`python` is fine **provided something does `import mcpyrate.activate` before that module is
imported** — it installs the import hook. `mcpyrate.activate` also exposes `activate()` /
`deactivate()` for turning the hook off around imports that do not need it.

**"I changed a macro and nothing happened" is the bytecode cache, not a bug.** The expander runs only
when the source file, or one of its macro-dependencies, has changed on disk — tracked by mtime,
recursively, `make`-style. `touch` the file, or `macropython -C`. Same cause when `step_expansion`
prints nothing: its whole output is a compile-time side effect, so if the expander does not run,
there is nothing to print.

## Reading an expansion

This is the part with no substitute, and the reason to reach for this skill rather than guess at what
a macro does.

- **`step_expansion`** (`mcpyrate.debug`) — expression *and* block macro; shows each expansion step.
  The one you want most of the time.
- **`stepr`** (`mcpyrate.metatools`) — for a *run-time AST value*, such as quasiquoted code. Expression
  form only, since values are referred to by expressions.
- **`step_phases`** (`mcpyrate.debug`) — for multi-phase compilation (`with phase`).
- **`StepExpansion`** (`mcpyrate.debug`, a *dialect*) — steps a dialect's source transformers, AST
  transformers and postprocessors.
- **`show_bindings`** / `format_bindings` — what macro names are actually bound in this module.
- `unparse(tree, debug=True, color=True)` and `dump(tree, color=True)`, both in `mcpyrate`'s top-level
  namespace, for looking at one specific tree.

Interpreting the output requires knowing what runs when — see "The import algorithm" in
`doc/compiler.md`.

## Macro-imports are not imports

`from module import macros, name` is a *marker* the expander consumes, and it behaves differently
from a normal import in ways that matter when reading code:

- It registers **macro bindings scoped to the module** the statement appears in.
- It must be at **top level** (the sole exception is at the top level of a `with phase`).
- `import *` does not work; you must name each macro. Aliasing does:
  `from module import macros, macroname as alias`.
- The expander **rewrites it to a plain `import module`**, always resolved to an absolute import. So
  the module *is* imported, and expanded code can refer to `module.thing` — that is the documented
  equivalent of `macropy`'s `expose_unhygienic`. (`mcpyrate` descends from `mcpy`, and this is one of
  the places it says so.)
- To use one of those functions as an ordinary function, import it ordinarily —
  `from module import name`, or a fully qualified `module.name`.
- Writing a macro that inspects `expander.bindings` for *other* macros: **compare the values**, not
  the names, since a use site may have aliased anything to anything.

## The four invocation forms

```python
with macro:   ...      # block:      receives the body
macro[...]             # expression: receives the subscript
@macro                 # decorator:  receives the decorated node
macro                  # identifier: receives the Name node itself
```

Expansion is **outside-in by default** — outermost node first — and each macro can choose to expand
before or after nested invocations.

## Quasiquotes, briefly

Quasiquotation is the Lisp idea of writing code as data with holes in it
([Wikipedia](https://en.wikipedia.org/wiki/Quasi-quotation)); `mcpyrate` gives it as macros, and
`doc/quasiquotes.md` is the reference. Reading order when you meet them:

| | |
|---|---|
| `q[...]` | quasiquote — the code becomes an AST |
| `u[...]` | unquote a simple run-time **value** |
| `n[...]` | name-unquote — parses a string of Python source and splices the AST. Designed for computed *name-like* things: identifiers, attributes, subscripts, nested in any syntactically legal combination (`n[f"kitties[{j}].paws[{k}].claws"]`) |
| `a[...]` | ast-unquote — splice in an AST value |
| `s[...]`, `t[...]` | ast-list / ast-tuple unquote |
| `h[...]` | **hygienic** unquote — capture a value (or macro) from the *definition* site |

**Two unrelated things are called `q` and `u`.** The `mcpyrate.quotes` pair above is the one that
appears in real code. `unpythonic.syntax.prefix` has its own `q`, `u` and `kw`, which are
*prefix-mode* markers — inside a `with prefix` block, `q` turns off the tuple-means-call
transformation and `u` turns it back on. Same letters, same vocabulary, unrelated semantics. `prefix`
is a component of the Listhell dialect (`with prefix, autocurry:`) and is not intended for production
code, so treat this as a reading aid: if `q` and `u` appear in a file, check which pair is imported
before assuming what they do. Neither project's docs cross-reference the other on this.

`h[]` is the one that carries the weight: it is how expanded code refers to something at the macro's
definition site without depending on the use site having imported it — the mechanism behind
[macro hygiene](https://en.wikipedia.org/wiki/Hygienic_macro). Its footprints are visible to tooling:
`is_captured_value` / `is_captured_macro` recognize them, which is why name-matching helpers check
for captures before treating a node as a plain name.

## "Macro expansion time" is a local notion

Worth internalizing, because it is where reasoning usually goes wrong. It is always five o'clock
*somewhere*: by the time a macro's own body runs, the macros used to *write* it (the `q` and friends)
are long gone, while its use site has not yet reached run time. Macros appearing in a macro's output
are just data until they are spliced in and expand afterwards.

So the question "is this expansion time or run time?" has to be asked **per source file** — and with
multi-phase compilation, per phase: the run time of phase `k+1` is the expansion time of phase `k`.

## What is in `unpythonic.syntax`

At overview depth; `unpythonic`'s `doc/macros.md` walks each one properly.

- **Bindings and sequencing.**
  - `let` — the basic form. `letseq` — sequential, so later bindings see earlier ones and shadow
    them on a repeated name; Scheme's `let*`, and it expands to nested `let`s. `letrec` — the
    bindings can see each other, so this is the one for locally defined mutually recursive
    functions; Scheme's `letrec`. Names within one `letrec` must be unique, and definitions are
    processed left to right: a definition may refer to any *earlier* one, and a callable value may
    refer to any of them, later ones included — which is what makes the mutual recursion work.
  - `where` — alternative syntax putting the bindings at the end, Haskell-style:
    `let[body, where[k0 := v0, ...]]`. Available for every expression-form let construct (`let`,
    `letseq`, `letrec`, `let_syntax`, `abbrev`). **Macro layer only** — the pure-Python `let` has no
    counterpart.
  - `do` — sequencing, Scheme's `begin`; `do0` returns the *first* value instead of the last,
    Scheme's `begin0`. What makes `do` more than `begin` is local variables: `local[name := value]`
    declares one and `delete[name]` removes it, each taking effect from the *next* item onward.
    Deletion is deliberately a `do` feature only; the `let` constructs do not support it.

    **In macro-using code, use `do`/`do0` and never `begin`/`begin0`.** `unpythonic` publishes
    `begin` and `begin0` too, as pure-Python functions in `unpythonic.seq` — and **the macro layer
    does not know about them**: there is not one reference to either anywhere in
    `unpythonic/syntax/`. So inside a macro block they are ordinary function calls and receive none
    of the transformations `do[]` gets. Being a function, `begin` also has its arguments evaluated
    before it runs, which is why `lazy_begin` / `lazy_begin0` exist taking thunks. The names are
    close enough to reach for by mistake and the failure is silent, so it is worth knowing before
    you need it — `begin`, `begin0`, `lazy_begin` and `lazy_begin0` each carry a `CAUTION` in their
    docstring saying exactly this.
  - `let_syntax` and `abbrev` — syntactic local bindings, in the tradition of Scheme's `let-syntax`.

  The `d` and `b` prefixes are worth spelling out, because the letters do not say much on their own:

  - **`@dlet` is *let over def*** — and it does what a Lisper would expect from that phrase, by
    analogy with *let over lambda*. The bindings live in a closure around the function, so they
    persist across calls, which makes it the natural spelling for a function with private state:
    `@dlet(count=0)` over a `def counter()` that increments `env.count` returns 1, 2, 3, …
  - **`@blet` is a relative of `@call`**, and gives block-local bindings by using a function as a
    scope boundary. It chains `@dlet` and `@call`: the block runs immediately, and the name that
    held the function is overwritten by the return value — exactly `@call`'s trick, with bindings
    added. So `@blet(x=9001)` over `def result(*, env): return env.x` leaves `result == 9001`.
- **Lambdas** — `multilambda` (multi-expression bodies), `namedlambda` (auto-naming, so tracebacks
  stop saying `<lambda>`), `fn` and `quicklambda` (underscore notation), `envify`.
- **Language features, the heavy end.**
  - `autocurry`; `lazify` (call-by-need); `tco` (automatic tail call optimization); `autoreturn`
    (implicit `return` in tail position).
  - `continuations` — `call/cc` for Python
    ([call/cc](https://en.wikipedia.org/wiki/Call-with-current-continuation) as in Scheme), with
    `call_cc`, `get_cc`, `iscontinuation`. **`multishot` builds on it**: a function becomes a
    multi-shot (rewindable) generator, meaningful only inside a `with continuations:` block, its
    yield spelled `myield` — which expands to `call_cc[get_cc()]`.
  - `monadic_do` — Haskell's
    [do-notation](https://en.wikipedia.org/wiki/Monad_(functional_programming)#do-notation), over any
    monad in `unpythonic.monads` or anything implementing `__rshift__` as monadic bind. Written
    `with monadic_do[M] as result:` over a single list literal, one item per do-block line:
    `name := mexpr` binds, a bare `mexpr` is sequencing-only (Haskell's `do { mx; ... }`, which is
    how `guard`-style filter lines are written), and the last item is the final monadic expression.
  - `forall` — the same idea specialized to the List monad, which is what makes it nondeterministic
    evaluation. Its docstring says so outright, and `doc/design-notes.md` contrasts it against the
    pure-Python `unpythonic.amb` as the clean design of that feature. It predates `monadic_do`
    (added in v2.1.0) and is kept for compatibility, so **reach for `monadic_do` in new code** —
    `forall` is the one you will meet when reading, not the one to write.
  - `prefix` — prefix call syntax, with its own `q`/`u`/`kw` markers (unrelated to the quasiquote
    operators of the same letters). A component of the Listhell dialect; not intended for production
    code.
- **Conditionals** — `aif` with its anaphoric `it`, and `cond`.
- **Debugging and notebooks** — `dbg` (prints expression source alongside value) and `nb`.
- **Testing** — `test`, `test_raises`, `test_signals`, `the`, `fail`, `error`, `warn`. Covered by the
  `testing-macro-enabled-python` skill; that layer is why `unpythonic` needs a macro-aware test framework
  at all.
- **Machinery you only touch when writing macros** — `letdoutil` (views over expanded/unexpanded
  `let`/`do` forms), `scopeanalyzer`, `nameutil` (`isx`, `getname`), `util`.

## Two caveats for tooling

- **Coverage reports read oddly, by design.** Block and decorator macros emit do-nothing nodes so the
  invocation line registers as covered; quasiquoted blocks show as covered even though they are
  quoted, not run; line numbers need not increase monotonically. `doc/troubleshooting.md` has a
  section per case. Do not "fix" these.
- **Packaging a macro-using app has its own failure modes** — `doc/troubleshooting.md` covers the
  setuptools and Debian cases. The short version is that the expander must be available and active
  wherever the code is compiled.
