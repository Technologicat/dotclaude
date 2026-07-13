---
name: project-setup
description: Reference for setting up a new Python project in the fleet, or modernizing an existing one — pyproject.toml and the PDM flow, Cython/meson-python editable install, lockfile policy, PEP 639 license metadata, the shared dev-dependency baseline, and the canonical ruff/cython-lint/flake8 configuration. Use when creating a new project, switching build system, adding or tuning lint config, or auditing an existing project's packaging metadata.
---

# Project setup

General reference for Python project setup and build-system modernization.
Covers pure-Python projects, Cython/meson-python projects, the shared dev
dependency baseline, and the canonical lint/style configuration.

Sibling skill: `ci-setup` covers CI workflow snippets, coverage, Codecov,
Dependabot, supply-chain hardening, and PyPI trusted-publisher setup. Lint
*configuration* lives here because it's a dev-setup concern first and a CI
concern second; `ci-setup` cross-references back.

---

## Pure Python (PDM)

Standard flow:

    pdm config venv.in_project true       # once, globally; harmless to repeat
    pdm use 3.14                          # or whichever Python version is current
    pdm install                           # creates .venv, installs dev deps

Per-project CLAUDE.md should note the target Python version and any
project-specific setup (editable entry points, pre-commit hooks, etc.).

---

## Cython / meson-python

Extra steps on top of the pure-Python flow, because meson-python's editable
install has a landmine.

### The recipe

    pdm config venv.in_project true
    pdm use 3.14                                                # or whichever version is current
    pdm install                                                 # dev deps into .venv
    pdm run python -m pip install --no-build-isolation -e .     # editable install

### Required dev deps (Cython-specific)

`[dependency-groups].dev` in `pyproject.toml` must include these three,
*in addition to* the shared baseline below:

    "meson-python>=0.16",
    "meson",
    "ninja",

These are *not* enough as PEP 517 `build-system.requires`. They must be
in the venv itself.

### Why `--no-build-isolation`

meson-python's editable loader rebuilds the extension on import. At
install time it captures `self._build_cmd`, which points at the `ninja`
binary available *during that install*.

- `pdm install` alone runs the build backend in a throwaway PEP 517 overlay
  (`/tmp/pdm-build-env-XXXX-overlay/bin/ninja`) that gets torn down afterwards.
  Result: first import after a `.pyx` edit fails with `FileNotFoundError: .../ninja`.
- `pip install --no-build-isolation -e .` reuses the venv directly, so the
  loader records stable `.venv/bin/...` paths.

Having meson+ninja in the venv itself (not just `build-system.requires`)
is what makes this work.

### PATH note

The editable loader needs `meson` and `ninja` on `PATH`. If rebuild errors
occur: `export PATH="$(pwd)/.venv/bin:$PATH"` — or just wrap commands in
`pdm run`.

### Rebuild workflow

After modifying `.pyx`/`.pxd` files, the next import auto-rebuilds the
extension. No manual reinstall needed.

Old CLAUDE.md files that say "re-run `pdm install` to rebuild" are wrong —
`pdm install` sees the lockfile as synced and does nothing.

### Canonical wording for per-project README.md

Copy into the "Development setup" section:

> ```bash
> git clone <repo-url>
> cd <project>
> pdm install                              # creates venv, installs dev deps
> pip install --no-build-isolation -e .    # editable install (needs venv activated)
> ```
>
> The `--no-build-isolation` flag is required for editable installs with
> meson-python — the on-import rebuild mechanism needs build dependencies
> (Cython, NumPy, meson, ninja) to remain available in the environment,
> not just in a throwaway build-time overlay.
>
> **PATH note:** The meson-python editable loader needs `meson` and `ninja`
> on `PATH`. If you get rebuild errors, ensure the venv's `bin/` is on the path:
>
> ```bash
> export PATH="$(pwd)/.venv/bin:$PATH"
> ```
>
> **Note on editable installs:** After modifying `.pyx` or `.pxd` files, the
> next import auto-rebuilds the Cython extension — no manual reinstall step
> needed. For a clean non-editable build, use `pip install .` and reinstall
> after changes.

### Canonical wording for per-project CLAUDE.md

Copy into the "Build and Development" section:

> ```bash
> pdm config venv.in_project true
> pdm use 3.14                                                # or whichever version is current
> pdm install                                                 # dev deps into .venv
> pdm run python -m pip install --no-build-isolation -e .     # editable install
> ```
>
> Prefix commands with `pdm run` if the venv is not active.
>
> **Why `--no-build-isolation`:** meson-python's editable loader rebuilds
> the extension on import, so it needs `meson`, `ninja`, and Cython to
> remain available in the venv — not just in a throwaway PEP 517 overlay.
> PDM's default `pdm install` runs the backend in an isolated overlay whose
> `ninja` path gets burned into the loader and then disappears, causing
> `FileNotFoundError: .../ninja` on import. The `pip install --no-build-isolation -e .`
> form reuses the venv directly and produces a loader with stable paths.
>
> **PATH note:** The editable loader needs `meson` and `ninja` on `PATH`.
> If you get rebuild errors: `export PATH="$(pwd)/.venv/bin:$PATH"` (or just
> use `pdm run`).
>
> **Editable installs:** After modifying `.pyx` or `.pxd` files, the next
> import auto-rebuilds the extension — no manual reinstall needed.
> Alternatively, for a clean non-editable build, use `pip install .` and
> reinstall after changes.

### Recommended meson.build globals for new Cython projects

Two one-liners that cost nothing and disarm future landmines. Place after
the `project(...)` call in the top-level `meson.build`:

    add_project_arguments('-D_USE_MATH_DEFINES', language: 'c')
    add_project_arguments('-X', 'language_level=3str', language: 'cython')

**`_USE_MATH_DEFINES`:** no-op on Linux/macOS; on MSVC it makes `<math.h>`
expose `M_PI` and friends. Defensive even if no current code uses them —
the failure mode is a cryptic Windows-only build break when a future
`cdef` helper uses a math constant.

**`language_level=3str`:** replaces per-file `# cython: language_level = 3`
directives so new `.pyx`/`.pxd` files can't silently fall back to Cython's
default.

Note: in Cython ≥ 3.0, `3str` and `3` are functionally identical —
`Cython/Compiler/Main.py` literally has `if level == '3str': level = 3`.
The `3str` name is preserved as the canonical Cython-3 form (it's what
Cython's own "directive not set" warnings suggest) and self-documents
that the choice was made explicitly for Python-3 semantics. Prefer it
for new projects; `3` in existing code is equally correct, so don't
churn over it.

### Compiler flags

**Don't hardcode architecture-specific flags** (`-march=native`, `-msse`,
`-msse2`, `-mfma`, `-mfpmath=sse`, etc.) in `meson.build` or anywhere else
in the build system. Meson's `buildtype=release` gives `-O2`, which is
correct for distributed wheels — a wheel built with `-march=native` on a
machine with AVX-512 would crash on any CPU without it.

Users building from source who want architecture tuning can set `CFLAGS`
themselves:

    CFLAGS="-march=native" pip install --no-build-isolation .

**One flag is enough: `-march=native`.** The old `-msse -msse2 -mfma -mfpmath=sse`
incantation is cargo-cult from the mid-2010s and all four flags are either
no-ops or redundant on modern x86_64:

- `-msse`, `-msse2`: part of the x86_64 architectural baseline. Every
  x86_64 CPU has them; GCC enables them unconditionally on x86_64.
- `-mfpmath=sse`: GCC's default on x86_64 is already `sse`.
- `-mfma`: implied by `-march=native` on any CPU that actually has FMA
  (Haswell 2013 and later — essentially every live machine). On pre-Haswell
  x86_64 it would fail because the CPU doesn't have FMA at all.

So: if the README shows a CFLAGS example, use `CFLAGS="-march=native"` and
nothing else. Legacy `setup.py` files in older projects may still carry
the full incantation — strip it down when modernizing.

---

## License metadata (PEP 639)

New projects declare their license the PEP 639 way from the start — an SPDX
expression plus a glob of the license file(s) — *not* the deprecated
`License ::` trove classifiers. This emits Metadata-Version 2.4
(`License-Expression` / `License-File`), which is the current standard.

In `[project]`:

    license = "BSD-2-Clause"            # an SPDX expression, quoted string (NOT {text = ...})
    license-files = ["LICENSE.md"]      # glob(s); whatever the repo's license file is actually named

And **remove** any `License :: ...` line from `[project].classifiers` — the SPDX
expression supersedes it, and the two together trip a setuptools/twine warning.

Notes:
- The SPDX string is an *expression*, so compound licenses work
  (`"GPL-2.0-or-later"`, `"MIT OR Apache-2.0"`). Verify the exact identifier
  against the actual `LICENSE`/`LICENSE.md` text — e.g. a 2-clause BSD file is
  `BSD-2-Clause`, not a bare `BSD`. Validate with
  `python -c "from packaging.licenses import canonicalize_license_expression as c; print(c('BSD-2-Clause'))"`.
- `license-files` points at the file(s) on disk; the path is relative to the
  project root and globs are allowed (`["LICENSE*"]`).
- **Backend support:** pdm-backend supports PEP 639 (leave it unpinned → latest).
  meson-python needs **>= 0.17** for `license-files`; bump the
  `build-system.requires` pin if a Cython project is older than that.
- Don't repeat the license in module docstrings — the project-level
  `LICENSE`/`LICENSE.md` is the single source of truth.

The whole fleet was migrated to this on 2026-06-10; this is the reference form
for anything new.

---

## Shared dev dependency baseline

Both pure-Python and Cython projects should have this in
`[dependency-groups].dev` in `pyproject.toml`:

    [dependency-groups]
    dev = [
        # Test
        "pytest>=8.0",
        "coverage",                # `coverage run -m runtests` / `coverage xml` for CI's coverage workflow
        "pip",                     # ensures `python -m pip` works in the venv

        # Linters (for local checks — CI also installs them separately)
        "ruff>=0.14.0",
        "flake8",                  # Emacs flycheck
        "autopep8",                # autoformat on save (Emacs)

        # Editor tooling (jedi-based IDE features in Emacs)
        "jedi>=0.19.2",
        "epc",                     # Emacs ↔ Python RPC
        "importmagic",             # auto-import suggestions

        # Release and CI-workflow tooling
        "build",                   # `python -m build --sdist` for pre-release sanity checks, matching the CI sdist job
        "pyyaml>=6.0.3",           # validate .github/workflows/*.yml from the dev venv without a separate pip install
    ]

**Why the editor tooling is per-project, not global.** With `venv.in_project true`,
Emacs (pyvenv / anaconda-mode) selects each project's `.venv` interpreter when you
open a file in that project, and flycheck/company then invoke tools through *that*
Python. So the editor-side tools must live in each project's venv, not just in a
global install:

- `flake8` — flycheck's linter (`flycheck-python-flake8-executable` resolves to the
  venv's `python3`);
- `autopep8` — format-on-save;
- `jedi` — completion, go-to-definition, eldoc;
- `epc` — the Emacs↔Python RPC bridge jedi/anaconda use;
- `importmagic` — auto-import suggestions.

They're in the dev baseline (rather than installed once globally) precisely so that
opening any fleet project in Emacs yields a working IDE with no per-project fiddling.
(`pip` is listed for the same reason: a guaranteed `python -m pip` inside the venv.)

Cython projects add on top:

    "Cython>=3.0",
    "cython-lint",
    "meson-python>=0.16",
    "meson",
    "ninja",

---

## Lockfile policy

Whether to commit `pdm.lock` depends on what the project *is*, not what build
system it uses:

- **Libraries — don't commit.** End users install the library as a dependency
  in *their* environment, so the library's lockfile is irrelevant to their
  build. CI fresh-resolves every run against the declared dep floors in
  `pyproject.toml`, which is a feature: it catches upstream breakage against
  declared compatibility ranges early — exactly what a library author wants
  to know. Add `pdm.lock` to `.gitignore`.

- **Apps — commit.** Apps get deployed; reproducible builds matter. Commit
  `pdm.lock` alongside `pyproject.toml`. Make sure `pdm.lock` is *not* in
  `.gitignore` (PDM's default `.gitignore` templates sometimes include it,
  and uv-based legacy setups typically gitignore `uv.lock` too — remove both
  lines when converting).

**Dual-use (library + CLI)** projects — pyan3, arxiv-api-search — count as
apps for lockfile purposes. The library-consumer case is unaffected by the
presence of a committed lockfile: consumers never see it, their resolver
works from the `pyproject.toml` declared deps. The CLI/contributor side
benefits from reproducible dev environments, so the tiebreaker goes to
"commit".

### Don't keep a fleet classification list here

A per-project list of who commits a lockfile is a cached copy of a fact that each
repo already answers authoritatively, and it rots. (There *was* one here, dated
2026-04-15; by mid-July it disagreed with reality for three of the eight projects
it named, and omitted a fourth entirely — worse than useless, because someone would
have "fixed" a repo to match it.)

Ask the repo instead:

```bash
git ls-files pdm.lock          # tracked → this project commits its lockfile
grep -n 'lock' .gitignore      # ignored → it doesn't
```

Then classify by what the project *is* — library, app, or dual-use — per the rule
above. If the repo disagrees with the rule, that's a finding to raise, not a
classification to record.

---

## Lint and style configuration

### Two-pass ruff in CI

CI runs ruff twice — once as a blocking check that ignores one rule, and
once as an advisory pass that checks only that rule:

    - name: Lint Python with ruff
      run: ruff check . --ignore SIM103
    - name: Lint advisories (non-blocking)
      run: ruff check . --select SIM103 || true

**Why:** `SIM103` (return-condition-directly) is useful advice but its
autofix damages multi-guard patterns where the nested `if` carries semantic
meaning separate from the outer guard. Running it as an advisory shows the
hints without failing the build.

If more rules go into the advisory bucket in the future, both steps should
grow in parallel (blocking pass adds `--ignore RULE`, advisory pass adds
`--select RULE`).

### cython-lint in CI (non-blocking)

    - name: Lint Cython
      run: cython-lint pylu/dgesv.pyx pylu/dgesv.pxd || true

Currently advisory-only because the tool has a known false positive on
relative cimports (`from . cimport dgesv` flagged as "imported but unused"
when the cimport is precisely what brings the `_c` functions into scope).

### Ruff config (canonical form)

Lives in each project's `pyproject.toml` under `[tool.ruff]`. Canonical
form — copy and adjust `target-version`:

    [tool.ruff]
    line-length = 130              # canonical default; bump per-project if clearly needed
    target-version = "py311"       # adjust per project — match requires-python floor
    exclude = [
        ".git",
        "__pycache__",
        "build",
        "dist",
        ".venv",
        "00_stuff",                # local non-tracked scratch area
    ]

    [tool.ruff.lint]
    select = ["E", "W", "F", "SIM"]
    ignore = [
        # pycodestyle
        "E203",   # whitespace before ':' — needed for slice alignment
        "E265",   # block comment should start with '# ' — commented-out code, markers
        "E301",   # expected 1 blank line — blank lines are semantic paragraph breaks
        "E302",   # expected 2 blank lines before def — same
        "E305",   # expected 2 blank lines after end — same
        "E306",   # expected blank line before nested def — same
        "E402",   # module level import not at top — conditional/deferred imports
        "E501",   # line too long — advisory, not enforced
        "E731",   # lambda assignment — closures are idiomatic in this codebase
        # flake8-simplify
        "SIM102",  # collapsible if — nested ifs often represent distinct semantic guards
        # Note: SIM103 (return condition directly) is intentionally NOT ignored here.
        # It is enabled as an advisory — CI runs it in a non-failing second pass.
        "SIM105",  # contextlib.suppress — try/except/pass is more flexible and explicit
        "SIM108",  # ternary instead of if/else — often less readable, no real gain
        "SIM114",  # combine if branches — match-casing style; autofix would damage semantics
        "SIM117",  # combine with statements — nesting shows parent/child relationships
        "SIM118",  # in-dict-keys — explicit .keys() marks the variable as a dictlike
        "SIM300",  # yoda conditions — natural reading order preferred
        "SIM910",  # dict.get with None default — explicit None documents programmer intent
    ]

    [tool.ruff.lint.per-file-ignores]
    "__init__.py" = ["F401", "F403"]  # re-exports via star-import

`per-file-ignores` is limited to `__init__.py`'s re-export pattern (PEP 8
`__all__` + `from submodule import *`). All other suppressions go at the
use site with `# noqa: CODE -- reason` (see `~/.claude/CLAUDE.md` rules).

**Line length:** 130 is the canonical default. Some projects may need
more (pydgq uses 200 because of long symbolic expressions in the numerics
code) — decide per project, but default to 130.

**Exclude note:** if a project has directories containing version-specific
syntax that would cause parse errors on older Pythons (e.g. a
`tests/test_code_312/` directory using 3.12+ `type` statements), add them
to `exclude` in `[tool.ruff]` *and* to the `exclude` line in any flake8
config. Both linters parse all files in their scope by default.

**Known gap: continuation-indent formatting is not checked, so broken formatting
reaches the default branch.** Ruff does not catch `E128` (continuation line
under-indented for visual indent) or its siblings — and *cannot*: as of 0.15.6 it
implements `E101` and `E111`–`E117` (the latter preview-gated) and the entire `E12x`
continuation-line family is absent. Ruff never ported those rules, treating them as
the formatter's job. `ruff format` would catch them but is Black-shaped and would
rewrite the fleet against the house style, which we don't want.

The fix is a second, check-only linter: `pycodestyle --select E12` as a blocking CI
step (a checker, not a fixer — it cannot rewrite), with `autopep8 --select E12
--in-place` as the local remedy. Tracked in `TODO_DEFERRED.md` in the `~/.claude`
repo, which records the verification. Not yet rolled out.

### Cython-lint config

Lives in `pyproject.toml` under `[tool.cython-lint]`. Canonical form
(currently identical in pylu and pydgq — the only two projects using it):

    [tool.cython-lint]
    max-line-length = 200
    ignore = ["E115", "E201", "E202", "E221", "E231", "E302", "W293", "W391"]

### Flake8 (legacy, Emacs flycheck)

Flake8 is kept around as an advisory linter for Emacs flycheck integration.
Not used in CI (ruff is the CI linter).

**Active config is the global `~/.config/flake8`** — the single source of truth
flycheck reads, shared across all projects and edited in one place. CI does not
use flake8 at all; `[tool.ruff]` in each `pyproject.toml` is the enforced linter.
The authoritative file is `~/.spacemacs.d/flake8` (version-controlled with the
Spacemacs config — that repo *is* the GitHub archive, no separate dotfiles copy
needed), symlinked as `~/.config/flake8` (and `~/.config/pep8`). flycheck is
pointed at the absolute path via `flycheck-flake8rc` in `~/.spacemacs.d/init.el`.

**Per-project archival copy: a file named `flake8rc` (no leading dot).** Several
projects (unpythonic, mcpyrate) commit a `flake8rc` so the exact style config
used travels with the repo — a documentary *snapshot*, not a competing source of
truth. The naming is deliberate **gotcha avoidance**: flake8 *auto-discovers*
`.flake8`, `setup.cfg`, and `tox.ini`, so a config in any of those silently
*overrides* the global on every `flake8 .` / CI run. The name `flake8rc` is **not**
in flake8's auto-discovery list, so the archived copy never affects CLI/CI runs;
flycheck can still read it explicitly via `flycheck-flake8rc`. Rules:

- **Do** archive a tracked `flake8rc` (non-dot) per project; keep its body the
  same as the global.
- **Don't** name it `.flake8` / use `setup.cfg` / `tox.ini` — those auto-load and
  hijack the global config.
- The global stays the active config; the project `flake8rc` is the travelling
  snapshot.

Fleet status: unpythonic and mcpyrate carry a `flake8rc`; raven had one from its
initial commit but dropped it when ruff was adopted (`89c76af`), so it currently
has none — a minor inconsistency, re-add if fleet uniformity is wanted.

**Canonical body of `~/.config/flake8`** (recover this verbatim if setting
up a new machine or if the file is lost):

    [flake8]
    # ignore silly style items
    ignore =
        # too complex (mcgabe)
        C901,
        # overhanging indent
        E126,
        # continuation line over-indented for visual indent
        E127,
        # block comment should start with #
        E265,
        # expected 1 blank line, found 0
        E301,
        # expected 2 blank lines before def
        E302,
        # expected 2 blank lines after def
        E305,
        # expected blank line before nested def
        E306,
        # module level import not at top of file (can cause problems when autopep8 applies it without thinking)
        E402,
        # line too long >79 chars
        E501,
        # multiple statements on one line (def)
        E704,
        # do not assign a lambda expression, use a def (because autopep8 applies it blindly)
        E731,
        # whitespace before ':' (false positive on alignment and slices; Black/Ruff agree)
        E203,
        # `global x` as intent marker (reading, not assigning)
        F824,
        # line break before binary operator (PEP 8 recommends Knuth's style, i.e. break before)
        W503,
        # line break after binary operator
        W504
    exclude = .git,__pycache__,docs/source/conf.py,old,build,dist,node_modules,instance,00_stuff,00_old

**Rule-overlap note:** The flake8 ignore list and the ruff ignore list are
deliberately close but not identical — flake8 has legacy rules like `C901`
(mccabe complexity), `E126`/`E127` (continuation indent), `E704` (multiple
statements), `W503`/`W504` (line break around binary operators) that ruff
doesn't expose the same way. When the house style evolves, update both
configs in parallel.
