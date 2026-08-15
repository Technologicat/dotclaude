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
whose bindings are readable only through the macro surface syntax. `unpythonic.dialects` is out for
the same reason. That is the fleet policy, and it is also where this tour stops. The obvious question
on reading the library's own docs is "why not the macros"; that is the answer.

## Contracts that are invisible at the call site

This is the part that has to be right, because it is what reading the calling code cannot show you.

- **The iterable utilities are lazy wherever they can be.** `flatten` says it outright — "returns a
  generator that yields the flattened output" — and so do most of `unpythonic.it`. A generator is
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

- **Several submodules share a name with a symbol, and which one you get is not guessable.** Where
  `__init__.py` star-imports the submodule, the symbol overwrites the module attribute, so
  `from unpythonic import llist` gives the **function** — likewise `let`, `fix`, `fup`, `gtco`,
  `assignonce`. Where it does not, the module wins: **`from unpythonic import env` gives you the
  module**, and `env(x=1)` then fails with "module is not callable". The class is
  `from unpythonic.env import env`, which is what working code does
  (`raven/common/bgtask.py:43`).

  So for a colliding name, import it explicitly from its submodule rather than from the package.
  The same shadowing is why enumeration must go through `sys.modules` rather than testing package
  attributes for module-ness — see `mcpyrate`'s `doc/troubleshooting.md`.

- **`memoize` also caches exceptions** — a repeat call with the same arguments re-raises *the same
  exception instance* — requires all arguments to be hashable, and requires `f` to be pure. It is
  thread-safe since v0.15.0 (exactly one thread computes any given result).

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
scoping idiom the fleet uses), `callwith`, and `Values` for structured multiple return values.
`arity` inspects callables — `arities`, `required_kwargs`, `resolve_bindings`. `dispatch` is
multiple dispatch in the CLOS/Julia sense (`@generic`, `@augment`, `@typed`). `fix` breaks recursion
cycles.

**Control flow.** `tco` is the trampoline (`@trampolined`, `jump`); `fploop` builds functional loops
on it (`@looped`, `@looped_over`). `ec` is escape continuations (`call_ec`, `catch`/`throw`).
`conditions` is the Common Lisp condition system — `signal`/`error`/`cerror`/`warn`, `handlers`,
`restarts`, `invoke` — resumable error handling, where a handler can tell the signaling code how to
continue instead of unwinding. `excutil` makes exception machinery expression-friendly (`raisef`,
`tryf`, `reraise`) and includes `async_raise`. `seq` is sequencing and piping (`begin`, `do`,
`pipe`/`piped`). `amb` is nondeterministic evaluation (`forall`, `choice`, `insist`/`deny`).

**Data and state.** `collections` holds `box`/`unbox` and `ThreadLocalBox`, `Some`, `frozendict`,
read-only and writable sequence `view`s, and `mogrify`. `fup`/`slicing` do functional (copy-on-write)
updates: `fupdate`, and the `fup(seq)[idx] << value` surface syntax. `env` is the namespace object
the fleet uses; `assignonce` is its write-once sibling. `dynassign` provides `dyn`, dynamic
(thread-local, dynamically-scoped) variables. `symbol` gives interned `sym` and uninterned `gensym`.
`singleton` is a `Singleton` base/mixin. `llist` is cons cells and linked lists, with the full
`car`/`cdr`/`caar`…`cddddr` accessor set.

**Odds and ends.** `misc` is the grab bag worth knowing by name — `si_prefix`, `timer`, `namelambda`,
`Popper`, `slurp`, `maybe_open`, `callsite_filename`, `getattrrec`/`setattrrec`, `UnionFilter`.
`numutil` is numerics — `almosteq`, `ulp`, `fixpoint`, integer partitions. `timeutil` is
`seconds_to_human`, `format_human_time`, `ETAEstimator`. `typecheck` is `isoftype`, a runtime check
that understands `typing` constructs. `lazyutil` is `Lazy`/`force` promises.

**Not part of the tour:** `unpythonic.net` is a REPL server, and `unpythonic.monads` mainly backs
`amb`. Neither is general-purpose utility code.

## Reach for these instead of writing your own

The recurring reinventions, with the fleet-relevant contract stated:

| Instead of writing | Use | Note |
|---|---|---|
| a KB/MB/GiB formatter | `si_prefix(n, precision=2, binary=False, separator=" ", always_separate=False)` | SI decimal (`k`…`Q`) or IEC binary (`Ki`…`Qi`), and the sub-unity prefixes (`m`…`q`) — so 10⁻³⁰ to 10³⁰, including the 2022 SI additions. `always_separate=True` keeps the spacing uniform when you append a unit, so `"512 B"` and `"1.5 KiB"` need no special case. `raven.common.filelisting.format_size` is the worked example. |
| "3h 25m elapsed" | `format_human_time`, `seconds_to_human` | |
| a progress ETA | `ETAEstimator(total, keep_last=None)` | |
| a mutable cell captured by a closure | `box` / `unbox`, `ThreadLocalBox` | |
| a "don't mutate this" dict constant | `frozendict` | enforces it, unlike the convention |
| a copy-then-modify of a tuple or dict | `fupdate`, or `fup(seq)[i] << v` | |
| `dict.fromkeys` dedup, sliding windows, batching | `uniqify`, `window`, `chunked` | lazy — see the contracts above |
| a float comparison with a hand-rolled epsilon | `almosteq`, `ulp` | |
| a thread-local "current X" global | `dyn`, `make_dynvar` | |
| a unique sentinel object | `sym("name")` (interned) or `gensym` | |
| `lambda`s that show as `<lambda>` in tracebacks | `namelambda` | |
| draining a `queue.Queue` | `slurp` | |
| a pop-while loop over a shrinking container | `Popper` | |

## Finding the rest

```
api-inventory --import unpythonic          # every public name, with signature and summary
api-inventory --names-only unpythonic      # just the names, when scanning for one
```

`unpythonic.llist` needs `--import` or a static resolver that follows the `__all__ = _exports` alias;
`api-inventory` handles both.
