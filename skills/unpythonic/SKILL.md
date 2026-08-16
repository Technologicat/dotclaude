---
name: unpythonic
description: What is in the `unpythonic` library and which of its contracts are invisible at a call site. Use before writing a general-purpose helper in a fleet project — SI/IEC number formatting, human-readable durations, ETA estimation, iterable utilities (windowing, chunking, uniqifying, flattening), immutable or functionally-updated containers, boxes, dynamic variables, symbols, memoization — since `unpythonic` very likely already has one. Also use when debugging a `memoize`, `curry`, or lazy-iterable surprise, or when deciding whether a construct belongs to the runtime layer or the (fleet-excluded) macro layer.
---

# unpythonic: what is in it, and what bites

`unpythonic` is Python with Lisp and Haskell habits. It ships the kitchen sink, so this is an
*overview* — enough that you know a thing exists and know the one property about it that would
otherwise bite. Signatures are what `help()` is for; run `api-inventory` (below) for the full list.

**Scope: the runtime layer only.** Raven's `CLAUDE.md:409` rules out the macro layer
(`unpythonic.syntax`) and anything that primarily serves as a macro backend — `let` / `lispylet`,
which exist mainly as a code-generation target for the macros. They *are* usable by hand (the
machinery runs on `env`, so a binding is just `env.x`), but clumsily: the body has to be a callable
taking an `env` parameter, which is exactly the noise the macro surface syntax removes.
`unpythonic.dialects` is out for the same reason. That is the fleet policy, and it is also where this
tour stops. The obvious question on reading the library's own docs is "why not the macros"; that is
the answer.

## Contracts that are invisible at the call site

This is the part that has to be right, because it is what reading the calling code cannot show you.

- **The iterable utilities are lazy wherever they can be.** That is the design intent, stated as a
  rule: what *can* be lazy is, and only what cannot be, isn't. `flatten` says it outright —
  "returns a generator that yields the flattened output". A generator is
  consumed once. Asking the same flattened result four questions answers the first one correctly and
  the other three from the leftovers, i.e. "no". Nothing at the call site looks wrong, and the
  failure is silent and plausible. If a result is consulted more than once, materialize it
  (`list(...)`) or make it restartable (`imemoize`).

- **`memoize` stores what the function returned, not what it produced.** Given a generator-returning
  function, the cached object is the *generator*, so the second call gets one that is already
  exhausted — and the emptiness then persists for the life of the cache. For generators use
  `gmemoize` (decorate the generator function; the whole sequence is retained, and a fresh instance
  can be taken at any time); for an existing iterable use `imemoize`, which makes it restartable.

  These two compound: `memoize` over something from `unpythonic.it` is the shape of the bug. Both
  halves look correct in isolation.

- **Import from the package, not through a submodule path.** The house style is
  `from unpythonic import x`, trusting the star-imports in `__init__.py` to have re-exported it.
  Do **not** write `import unpythonic.somemod` and then call `unpythonic.somemod.func(...)`.

  **The reason is what a missed rewrite costs, not that dotted calls are generally invisible.**
  The general matcher, `syntax/nameutil.py`'s `isx`, defaults to `accept_attr=True` and matches on
  the final attribute name — its docstring says this exists "to support both from-imports and
  regular imports of `somemodule.x`". Every path that matches an *imported callable* uses that
  default, so `somemodule.jump(...)` is recognized (`tailtools` for `jump` and `trampolined`,
  `autocurry` for `curry`). The bare-name-only paths mostly match things that can only be bare
  anyway: `prefix`'s `q`/`u`/`kw` markers, `let` binding targets, `autoref`'s internal markers.

  What is left is a thin but real margin, and it is one-sided. `syntax/util.py`'s escape-
  continuation check documents itself with "**CAUTION**: Only bare-name references are supported."
  When a construct *is* missed, the macros rewrite it because it needs rewriting, so the result is
  typically a crash, or worse, silently wrong behaviour — and it surfaces only when the calling
  code is later macro-enabled, long after the import was written. Against that, the bare-name form
  costs nothing and spares you having to know which matcher a given construct goes through. That
  is why the habit holds in code with no macros in it today.

  Note this *inverts* the dotted-import preference that applies to a project's own modules
  (`raven/CLAUDE.md:414`). The reason is specific to `unpythonic`, and does not generalize.

- **The one exception, and it is forced: `from unpythonic.env import env`.** Several submodules
  share a name with a symbol, and which one you get depends on whether `__init__.py` star-imports
  that submodule. Where it does, the symbol overwrites the module attribute, so
  `from unpythonic import llist` gives the **function** — likewise `let`, `fix`, `fup`, `gtco`,
  `assignonce`. `.env` is never star-imported, so there the module wins:
  `from unpythonic import env` hands you a module, and `env(x=1)` fails with "module is not
  callable". Working code spells it `from unpythonic.env import env` (`raven/common/bgtask.py:43`).

  The same shadowing is why any tool enumerating the package must go through `sys.modules` rather
  than testing package attributes for module-ness — see `mcpyrate`'s `doc/troubleshooting.md`.

- **`memoize` also caches exceptions** — a repeat call with the same arguments re-raises *the same
  exception instance* — requires all arguments to be hashable, and requires `f` to be pure.

- **Assume thread safety; the docstring will say when there is none.** The library aims at
  obsessive correctness, and that includes being thread-safe throughout rather than in the places
  someone got around to. Scanning the runtime layer for disclaimers turns up none — only positive
  statements (`environ`, `gmemo`, `fix`, `symbol`, `singleton`, and `memoize` since v0.15.0, where
  exactly one thread computes any given result). So the useful habit is the reverse of the usual
  one: do not go hunting for a guarantee, but do read the docstring of anything you are about to
  share between threads, because that is where an exception would be recorded.

## The tour

**Iterables and sequences.** `it` is more batteries for `itertools` (~44 exports: `window`,
`chunked`, `uniqify`/`uniq`, `partition`, `take`/`drop`, `first`/`second`/`nth`/`last`, `flatten`
and friends, `within`, `powerset`, `interleave`, `inn` for a terminating containment check) — lazy
where possible. `fold` is the fold/scan family in both directions (`foldl`/`foldr`, `scanl`/`scanr`,
`unfold`, plus `prod`, `minmax`, `running_minmax`). `mathseq` gives lazy mathematical sequences with
termwise infix arithmetic — `s(1, 2, ...)` notation, `primes()`, `fibonacci()`, Cauchy products.
`gmemo` is the generator-aware memoization above; `gtco` is TCO for generators.

**Functions.** `fun` is the combinator kit (~30 exports): `memoize`, `curry`, `composer`/`composel`
and their curried and iterable-reading variants, `flip`, `rotate`, `andf`/`orf`/`notf`,
`identity`/`const`, `withself` for self-referential lambdas. `funutil` has `call` (the `@call`
scoping idiom the fleet uses), `callwith`, and `Values` for structured multiple return values —
including *named* ones, the missing counterpart of named arguments, which earns its keep in a
compose chain where positional returns stop being self-describing.
`arity` inspects callables — `arities`, `required_kwargs`, `resolve_bindings`. `dispatch` is
multiple dispatch in the CLOS/Julia sense (`@generic`, `@augment`, `@typed`). `fix` breaks recursion
cycles in *pure* functions.

**Control flow.** `tco` is the trampoline (`@trampolined`, `jump`); `fploop` builds functional loops
on it (`@looped`, `@looped_over`). `ec` is escape continuations (`call_ec`, `catch`/`throw`).
`conditions` is the Common Lisp condition system — `signal`/`error`/`cerror`/`warn`, `handlers`,
`restarts`, `invoke` — resumable error handling, where a handler can tell the signaling code how to
continue instead of unwinding. `excutil` makes exception machinery expression-friendly (`raisef`,
`tryf`, `reraise`) and includes `async_raise`. `seq` is sequencing and piping (`begin`, `do`,
`pipe`/`piped`) — note that `begin`/`begin0` are invisible to the macro layer, so code that is ever
macro-enabled must use the `do[]`/`do0[]` macros instead; see the `macro-enabled-python` skill. `amb` is nondeterministic evaluation (`forall`, `choice`, `insist`/`deny`), and is **not for
production code** — the library's own `doc/design-notes.md` calls `unpythonic.amb.forall` "overly
complicated, to avoid macros" and names the macro version, `unpythonic.syntax.forall`, as the clean
design of the same feature. Reach for the pure-Python one only where the macro layer is off limits,
and know what you are accepting.

**Data and state.** `collections` holds `box`/`unbox` and `ThreadLocalBox`, `Some`, `frozendict`,
read-only and writable sequence `view`s, and `mogrify`. `fup`/`slicing` do functional (copy-on-write)
updates: `fupdate`, and the `fup(seq)[idx] << value` surface syntax. `env` is the namespace object
the fleet uses; `assignonce` is its write-once sibling, and is **not recommended** — the macro layer
supports `env` far more thoroughly, so `assignonce` is the one you give up when you want the rest. `dynassign` provides `dyn`, dynamic
(thread-local, dynamically-scoped) variables. `symbol` gives interned `sym` and uninterned `gensym`.
`singleton` is a `Singleton` base/mixin. `llist` is cons cells and linked lists, with the full
`car`/`cdr`/`caar`…`cddddr` accessor set.

**Odds and ends.** `misc` is the grab bag worth knowing by name — `si_prefix`, `timer`, `namelambda`,
`Popper`, `slurp`, `maybe_open`, `callsite_filename`, `getattrrec`/`setattrrec`, `UnionFilter`.
The `timer` snippet is worth memorising, since it recurs: `with timer() as tim: ...` and then
`tim.dt`, measured with `perf_counter`.

`numutil` is numerics — `almosteq`, `ulp`, `fixpoint`, integer partitions. `timeutil` is
`seconds_to_human`, `format_human_time`, and `ETAEstimator` — the fleet's way of showing a
human-readable ETA, averaging over a ring buffer whose size `keep_last` tunes. `typecheck` is `isoftype`, a runtime check
that understands `typing` constructs. `lazyutil` is `Lazy`/`force` promises.

**Not part of the tour:** `unpythonic.net` is a REPL server. `unpythonic.monads` is largely a
self-contained experiment and a body of teaching code; its `List` is what backs `amb`. Neither is
general-purpose utility code you would reach for while building something else.

## Reach for these instead of writing your own

The recurring reinventions, with the fleet-relevant contract stated:

| Instead of writing | Use | Note |
|---|---|---|
| a KB/MB/GiB formatter | `si_prefix(n, precision=2, binary=False, separator=" ", always_separate=False)` | SI decimal (`k`…`Q`) or IEC binary (`Ki`…`Qi`), and the sub-unity prefixes (`m`…`q`) — so 10⁻³⁰ to 10³⁰, including the 2022 SI additions. `always_separate=True` keeps the spacing uniform when you append a unit, so `"512 B"` and `"1.5 KiB"` need no special case. `raven.common.filelisting.format_size` is the worked example. |
| "3h 25m elapsed" | `format_human_time`, `seconds_to_human` | |
| a progress ETA | `ETAEstimator(total, keep_last=None)` | |
| a mutable cell captured by a closure | `box` / `unbox`, `ThreadLocalBox` | |
| a "don't mutate this" dict constant | `frozendict` | enforces it, unlike the convention. Predates the builtin `frozendict` that [PEP 814](https://peps.python.org/pep-0814/) adds to `builtins` in 3.15, and runs on older Pythons. Neither subclasses `dict`, and that is the load-bearing choice rather than a coincidence: `dict` is registered as a `MutableMapping`, so a subclass would advertise mutability to every `isinstance` check and inherit `__hash__ = None`. Both inherit from `object` and register as `Mapping` + `Hashable` instead — so the eventual migration is a rename, not a change of contract |
| a copy-then-modify of a tuple or dict | `fupdate`, or `fup(seq)[i] << v` | |
| `dict.fromkeys` dedup, sliding windows, batching | `uniqify`, `window`, `chunked` | lazy — see the contracts above |
| a float comparison with a hand-rolled epsilon | `almosteq`, `ulp` | |
| a thread-local "current X" global | `dyn`, `make_dynvar` | |
| a unique sentinel object | `sym("name")` (interned) or `gensym` | Two properties a bare `object()` lacks: a human-readable `repr`, and survival across a pickle roundtrip — gensyms included |
| `lambda`s that show as `<lambda>` in tracebacks | `namelambda` | A traceback shows a lambda as `<lambda>` by default; this makes it show the name you gave, patching three separate places so the name holds everywhere |
| draining a `queue.Queue` | `slurp` | |
| a pop-while loop over a shrinking container | `Popper` | |

## Finding the rest

```
api-inventory --import unpythonic          # every public name, with signature and summary
api-inventory --names-only unpythonic      # just the names, when scanning for one
```

`unpythonic.llist` needs `--import` or a static resolver that follows the `__all__ = _exports` alias;
`api-inventory` handles both.
