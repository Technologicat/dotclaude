---
name: unpythonic-macro-testing
description: Reference for writing tests for macro-enabled Python code using `unpythonic.test.fixtures` — the test framework unpythonic provides (name kept for backward compat despite being a slight understatement). Covers the `session` / `testset` / `runtests()` structure, the `test[]`, `test_raises[]`, `test_signals[]`, `warn[]` and `the[]` macros, the load-bearing Pass/Fail/Error distinction, and why test code under a macro expander needs different fixtures than ordinary pytest code. Use when writing or debugging tests for code that uses mcpyrate macros or unpythonic macros, when reading a Fail/Error report from this framework, or when scaffolding a test module for a macro-using project.
---

# Testing macro-enabled Python with `unpythonic.test.fixtures`

Part of unpythonic's **public API** (`unpythonic.test.fixtures`, `unpythonic.test.runner`), and reusable by any project that writes macro-enabled tests — not just unpythonic itself.

**Canonical reference: `~/Documents/koodit/unpythonic/CLAUDE.md`** (the "Running tests" section and its `unpythonic.test.fixtures` subsection). This skill is the discoverability layer and the 80% case; the upstream file is the source of truth and goes deeper, in particular on `the[]` anti-patterns. Read it when doing anything beyond first-pass scaffolding.

## Why not pytest

pytest's assertion rewriting operates on the `assert` statement, and test code that runs under a macro expander doesn't compose cleanly with it. `unpythonic.test.fixtures` sidesteps the conflict: rather than overriding `assert`, it provides **macros** that build the assertion at the AST level and route results through mcpyrate's condition system.

## Test module skeleton

```python
from ..syntax import macros, test, test_raises, fail, the  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

def runtests():
    with testset("identity function"):
        test[identity(42) == 42]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
```

Every test module exports `runtests()`; a project-level `runtests.py` discovers and runs them. Tests are grouped into `testset()` context managers, which nest.

The runner does **not** need the `macropython` wrapper — it activates macros via `import mcpyrate.activate`.

## The assertion macros

- `test[expr]` — passes if `expr` is truthy.
- `test_raises[cls, expr]` — passes if `expr` raises exactly `cls`.
- `test_signals[cls, expr]` — the conditions-and-restarts analogue of `test_raises`.
- `warn[msg]` — advisory; does not count toward Pass/Fail/Error and does not fail the testset. Use for version gates and optional-dependency skips.
- `returns_normally(expr)` — a plain function, for "this just shouldn't blow up".

## Pass / Fail / Error — the distinction is load-bearing

- **Pass** — the test ran and met its expectation.
- **Fail** — the test ran to completion but the expectation didn't hold. "Your code is wrong."
- **Error** — the test did *not* run to completion; an unhandled exception or condition escaped the `test[...]` expression itself. The test never got to judge the expectation, so this means something is broken in a way nobody predicted.

**Always look at Errors first.** A Fail tells you which expectation broke; an Error only tells you control flow went somewhere unexpected, and the count alone won't say where — the traceback above the summary line will.

## Capturing values with `the[]`

When a test fails you want to see what the interesting subexpression actually evaluated to. `the[...]` marks a subexpression for capture, and the failure message reports its source text and runtime value.

If the top-level expression of `test[]` is a comparison and no explicit `the[]` appears, **the leftmost term is captured implicitly** — so `test[x == 42]` already reports `x`. Reach for an explicit `the[]` only when you want a *different* term:

```python
test["green tea" == the[vert]]     # capture the RHS
test[f(the[a]) == g(the[b])]       # capture both, in evaluation order
test[the[a] < the[b] < the[c]]     # chained comparison: wrap every term you'd want to see
```

Any explicit `the[]` anywhere in the expression **disables** auto-capture.

Decide by asking *"what value on failure would I actually want to see?"* — not *"is `the[]` redundant?"*. The leaf is enough when it's self-explanatory (`timer.dt == 0.0`); wrap the container when the leaf is lossy (`test[the[reply]["status"] == "ok"]` shows you the whole dict, including the `"reason"` field, instead of just `"failed"`).

The common anti-pattern is wrapping the whole assertion — `test[the["X" in out]]` captures the *boolean result*, which tells you nothing. Write `test["X" in the[out]]` instead. The upstream reference lists the full set; pattern-match your draft against it before committing.

`the[]` is not supported inside `test_raises`, `test_signals`, `fail`, `error`, or `warn`.

Naming: in test code, avoid `the`-prefixed variable names — `the[theconstant]` isn't English. Use `constant_node` instead.

When grepping for it, anchor the search: `\bthe\[`.
