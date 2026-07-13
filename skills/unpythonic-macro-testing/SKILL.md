---
name: unpythonic-macro-testing
description: Reference for writing tests for macro-enabled Python code using the test framework unpythonic provides — `unpythonic.test.fixtures` (the assertion macros) and `unpythonic.test.runner` (reusable test discovery and running, for any project, not just unpythonic). Covers the `session` / `testset` / `runtests()` structure, a downstream project's `runtests.py` via `discover_testmodules` / `run`, version-suffix gating of test modules, the `test[]`, `test_raises[]`, `test_signals[]`, `warn[]` and `the[]` macros, the load-bearing Pass/Fail/Error distinction, and why test code under a macro expander needs different fixtures than ordinary pytest code. Use when writing or debugging tests for code that uses mcpyrate macros or unpythonic macros, when setting up a test runner for a macro-using project, when reading a Fail/Error report from this framework, or when scaffolding a test module.
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

Every test module exports `runtests()`. Tests are grouped into `testset()` context managers, which nest.

## The runner is reusable too — don't hand-roll discovery

`unpythonic.test.runner` is part of the public API, alongside the fixtures. It provides `discover_testmodules(path, prefix="test_", suffix=".py")` and `run(testsets)`, so a downstream project's top-level `runtests.py` is a handful of lines:

```python
import os
from unpythonic.test.runner import discover_testmodules, run

import mcpyrate.activate  # noqa: F401

def main():
    testsets = [("regular code", discover_testmodules(os.path.join("mypackage", "tests"))),
                ("macros", discover_testmodules(os.path.join("mypackage", "syntax", "tests")))]
    return run(testsets)

if __name__ == '__main__':
    if not main():
        raise SystemExit(1)
```

Each entry in `testsets` is a `(label, modules)` pair, so the top-level report is grouped by whatever division makes sense for the project.

Two things this buys you for free:

- **Version-suffix gating.** A module named `test_foo_3_11.py` is automatically skipped, with a warning rather than a failure, on Pythons older than 3.11. Use the suffix instead of writing version guards by hand.
- **No `macropython` wrapper needed.** The top-level script is ordinary Python; `import mcpyrate.activate` switches macro expansion on for everything it subsequently imports. Run it with plain `python3 runtests.py`.

## The assertion macros

- `test[expr]` — passes if `expr` is truthy.
- `test_raises[cls, expr]` — passes if `expr` raises exactly `cls`.
- `test_signals[cls, expr]` — the conditions-and-restarts analogue of `test_raises`.
- `warn[msg]` — advisory; does not count toward Pass/Fail/Error and does not fail the testset. Use for version gates and optional-dependency skips.
- `returns_normally(expr)` — for "this just shouldn't blow up". It's a *predicate*, not an assertion, so it goes **inside** a `test[]`:

  ```python
  test[returns_normally(dothing())]
  ```

  It passes if `expr` runs to completion without raising or signaling. Being a plain function rather than a macro, it composes into a larger assertion where that's useful — but on its own, outside a `test[]`, it asserts nothing.

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

Decide by asking *"what value on failure would I actually want to see?"* — not *"is `the[]` redundant?"*.

The leaf is enough when it's self-explanatory: `test[timer.dt == 0.0]` reports `timer.dt`, and that's the whole story. Wrap the *container* when the leaf is lossy — when knowing the value that failed doesn't tell you why:

```python
test[the[response]["status"] == "ok"]
```

Auto-capture would have reported `response["status"]`, i.e. `"failed"` — true, and useless. Capturing `response` shows the whole dict, so whatever other keys the failure came with are in front of you.

The common anti-pattern is wrapping the whole assertion — `test[the["X" in out]]` captures the *boolean result*, which tells you nothing. Write `test["X" in the[out]]` instead. The upstream reference lists the full set; pattern-match your draft against it before committing.

`the[]` is not supported inside `test_raises`, `test_signals`, `fail`, `error`, or `warn`.

Naming: in test code, avoid `the`-prefixed variable names — `the[theconstant]` isn't English. Use `constant_node` instead.

When grepping for it, anchor the search: `\bthe\[`.
