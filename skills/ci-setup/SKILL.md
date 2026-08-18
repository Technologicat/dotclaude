---
name: ci-setup
description: Reference for setting up or modernizing CI for a Python project in the fleet — GitHub Actions, test matrix, how CI installs dependencies (pdm install vs raw pip vs hand-picked subset), pytest coverage and Codecov, cibuildwheel for Cython extensions, Windows MSVC activation, automated PyPI publishing via trusted publishers, and supply-chain hardening (pinning actions to commit SHAs, least-privilege GITHUB_TOKEN permissions, vetting action bumps). Use when configuring CI workflows, adding coverage, fixing CI failures, hardening CI / pinning actions to SHAs / setting workflow token permissions, or scaffolding a new project's CI — and also when **adding or changing a dependency**, especially a test dependency: in projects whose CI installs deps by hand (Cython/meson-python projects, and Raven), the dep must be added to the CI install step as well as to pyproject.toml, and nothing enforces that.
---

# CI/Coverage setup

Reference for CI/coverage setup across projects.

Sibling skill: `project-setup` covers the build system and linter config.

**Copy from `chandra` for pure Python, `pylu` for Cython/meson-python.** Both are
live, so their workflows are exercised on every change; chandra's `ci.yml` and
`coverage.yml` carry the full shape including the tag-gated `publish` job and the
Codecov upload. Read the real file next to this skill rather than reconstructing
one from the snippets here — the snippets explain *why*, and go stale faster than
the workflows do. (Don't reach for a deprecated project as the example: a frozen
one has nothing forcing it to stay current. `arxiv-api-search` filled this role
until 2026-08-18 and had drifted — stale badge, no `build-dist` job — while still
being cited for it.)

## How does CI install dependencies?

There are three patterns in the fleet, and picking the right one is the first decision.
Local dev always uses `pdm install` (which reads `[dependency-groups].dev`); what varies
is CI.

| Pattern | Projects | CI install |
|---|---|---|
| **`pdm install`** | pure-Python PDM projects | `pip install pdm` → `pdm install`. Dep groups work; nothing to hand-maintain |
| **Raw pip + build deps** | Cython / meson-python projects | `pip install meson-python meson ninja Cython numpy pytest` → `pip install --no-build-isolation -e .` |
| **Raw pip + hand-picked subset** | the heavy-dependency app (currently only Raven) | explicit list → `pip install -e . --no-deps` |

**If the project is pure Python, just use `pdm install` in CI.** It reads the dep groups,
so there is no second list to maintain. That's the default, and most of the fleet does it.

**Cython/meson-python projects can't**, because the editable install needs
`--no-build-isolation` (so meson picks up the right compiler and the pinned build deps),
which means the build deps must already be in the environment. Raw pip is a consequence of
the build system, not a preference. Note the constraint underneath: PEP 735
`[dependency-groups]` are invisible to raw `pip` — only PDM and uv implement them — so a
pip-based job *must* list what it needs.

### Never let PDM install its own interpreter in CI

`setup-python` has already put the matrix's interpreter on PATH by the time the install step
runs. Point PDM at that one:

```yaml
    - name: Create in-project virtualenv and install dependencies
      run: |
        pdm use -f "$(python -c 'import sys; print(sys.executable)')"
        pdm install
```

Two details, each of which cost a red CI run to learn:

- **`-f` (`--first`) is load-bearing**: it means "select the first matched interpreter — no
  auto install". Without it PDM may go fetch one.
- **Ask Python for its own path; do not use `which`.** These steps run under Git Bash on
  Windows, where `which python` answers with an MSYS path like `/c/hostedtoolcache/...`, and
  PDM is a native Windows program that cannot resolve it. `sys.executable` is a native path
  everywhere. This breaks *only* the Windows jobs, so a Linux-only matrix will not reveal it.

**What this replaces, and why it matters when adding a Python version.** The old form was
`pdm python install <version>`, which downloads a second interpreter from PDM's own index.
That index carries no prerelease builds, so the step fails for a version at rc — which is
exactly the moment a new Python is added to the matrix, and the failure looks like "3.15 is
broken" when in fact `setup-python` had installed 3.15 successfully in the same job.

It also retires a related wart. Where a matrix includes PyPy, CI spells it `pypy-3.11` while
PDM spells it `pypy@3.11`, so those workflows carried a step that rewrote the string through
`tr - @` into an environment variable. With nothing being downloaded there is nothing to
translate, and the step can go. (Fleet-wide as of 2026-08-17; `pyan` never had the pattern —
plain `pdm install` picks up the ambient interpreter by itself, which works but leaves the
choice implicit.)

**The hand-picked subset is a last resort, and exactly one project needs it.** The reason is
CI cost: Raven's full dependency tree is multi-gigabyte, and a matrix installs it *once per
entry, on every push*. That is the whole argument — the install would dominate the run, over
and over, to test code that mostly doesn't touch it.

So Raven's CI installs an explicit list instead (with CPU-only torch wheels from PyTorch's
own index, rather than the CUDA build), installs the package with `pip install -e . --no-deps`
so the rest of the tree is never resolved, and runs `pytest -m "not ml"` to skip the tests
that need real model weights.

A second benefit, worth knowing because it isn't obvious: since the heavy TTS stack is never
installed in CI, the matrix can add **macOS and Windows** runners without depending on that
stack having wheels for them. The torch CPU index carries wheels for all three OSes, so the
install line works unchanged. (This is about the portability of the *CI job*, not of the
project: the full install resolves fine for users on the supported Python versions — that's
what "supported" means. The project's Python cap comes from the TTS stack itself, and the
matrix respects it either way.)

**The cost of that last pattern is a second, hand-maintained list.** Add a test dep and you
must add it in two places — `[dependency-groups].dev` and the CI pip step — with nothing
enforcing the overlap: a test importing something CI doesn't install fails only on push.
That is why it's reserved for the project that genuinely can't do without it, and why both
Raven's `pyproject.toml` and its workflow carry comments explaining the divergence. Without
those, the next reader "fixes" the discrepancy and reintroduces the problem.

### Catch that failure locally, in about ten seconds

A dev machine has the full stack, so an import CI can't satisfy is invisible there. Block the
modules CI omits and run collection:

```python
import sys, importlib.abc, pytest

BLOCKED = {"sseclient", "spacy", "transformers"}   # what CI's subset omits — check, don't guess

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ModuleNotFoundError(f"No module named {fullname!r}")
        return None

sys.meta_path.insert(0, Blocker())
raise SystemExit(pytest.main(["<pkg>/tests/", "--collect-only", "-q", "-p", "no:cacheprovider"]))
```

Exit 0 means collection survives. **Derive `BLOCKED` from the workflow, not from memory** — a
too-broad list produces failures that aren't real, which is worse than no check because it
sends you fixing the wrong thing. Read *every* install step: things arriving from a separate
index (torch from PyTorch's CPU wheels) or from the requirements file are present, not missing.

**`--collect-only` is the point, not a shortcut.** The failure mode this catches is
*collection*, and it is much worse than a failing test: an import error inside a `conftest.py`
takes down the whole directory, so a package's entire suite vanishes rather than the few tests
that needed the missing module. Individual test modules can guard with
`pytest.importorskip`; a conftest cannot, because everything beside it depends on it. So a
conftest must import only what CI installs — and if it needs more, it needs a copy of the data
plus a drift test parked behind some *other* module's `importorskip`.

## Components

### GitHub Actions — Test matrix (`.github/workflows/ci.yml`)

- **Trigger:** push + PR to the repo's **default branch**, and workflow_dispatch. That branch is not the same across the fleet — see "Default branch: `master` or `main`" below
- **`name: CI`**, in the file `ci.yml`, and the coverage workflow is `name: Coverage` in `coverage.yml`. Fleet-wide, no exceptions — the name is what `gh run list --json name` selects on, and CLAUDE.md requires selecting the run *by workflow name* before tagging a release. Every inaccuracy in a name is therefore a trip hazard on the check that keeps a red run from burning a version number. Do not name it after a subset of what it does: these workflows lint, test, build and publish, so `Tests` is wrong, and `Python package` (the GitHub starter-workflow default) says nothing at all. Both were live in the fleet until 2026-08-18. Note the *badges* key on the filename, not the name — `img.shields.io/github/actions/workflow/status/OWNER/REPO/ci.yml` — so renaming `name:` is free, while renaming the file needs the README updated with it
- **Matrix:** all supported Python versions, `fail-fast: false`
- **Steps:** checkout → setup-python → install deps → ruff lint → pytest
- Use `actions/checkout` and `actions/setup-python` — **SHA-pinned** (see "Pin GitHub Actions to commit SHAs"), like every action
- **Top-level `permissions: contents: read`** (after `on:`, before `jobs:`) — least-privilege `GITHUB_TOKEN` (see "Least-privilege `GITHUB_TOKEN` permissions")
- For pre-release Python versions: `allow-prereleases: true`
- **Install deps by whichever of the three patterns fits** (see above). In a raw-pip job, install pytest alongside the build deps; in a `pdm install` job it comes from `[dependency-groups].dev` for free. Either way, **don't use `[project.optional-dependencies].test`** — pytest is dev tooling, not a published library feature (see "Test dependencies in CI" below).
- Install ruff and cython-lint separately in the lint job — they're CI tools, not project test deps. (They also live in `[dependency-groups].dev` so local dev has them.)
- **Cython extensions on Windows:** add an `ilammy/msvc-dev-cmd` step (SHA-pinned, like every action) before the build step, conditional on `runner.os == 'Windows'`. Without it, meson picks up MinGW-w64 gcc and the resulting `.pyd` files link to DLLs that aren't on the runtime search path. See "Windows CI for Cython extensions: force MSVC" below for the full story.

### Default branch: `master` or `main`

**The fleet is split, so don't assume.** The older projects are on `master`; the ones
started later are on `main`. Getting this wrong means workflows that never trigger and
badges that render as "unknown" — both of which fail *quietly*.

**Ask GitHub:**

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
```

Authoritative. It needs the network, which is normally a non-issue — a cloud-hosted agent
is online whenever it's working at all, and you're pushing to these repos anyway.

**Don't** use `git symbolic-ref --short HEAD`: it answers a different question — *which
branch am I on* — and cannot tell you whether that happens to be the default one. It's
right whenever you're on `master`/`main`, which is often, and silently wrong when you're
not. A command that's correct only when you already know the answer is no help.

**Don't rely on `git rev-parse --abbrev-ref origin/HEAD` either.** It's the textbook
offline answer, but that ref is written by `git clone` — and most of these repos were born
here (`git init`, then pushed to a new GitHub repo), so they never had a clone to write it.
It is unset in 7 of 9, where it prints `origin/HEAD` and an error instead of a branch name.
If you want it locally, `git remote set-head origin -a` populates it — which needs the
network anyway, so you may as well have asked `gh`.

(While you're here: the *directory* name is not the repo name either —
`~/Documents/koodit/wlsqm` is `Technologicat/python-wlsqm`. Read `git remote -v`.)

### Lint configuration — see the `project-setup` skill

Canonical ruff, cython-lint, and flake8 configs (and the rationale behind
each ignore) live in the `project-setup` skill under "Lint and
style configuration". That skill is the single source of truth for lint
rules. CI just runs `ruff check .` and `cython-lint` against the configs in
each project's `pyproject.toml`.

Note that `cython-lint` is only needed for Cython projects.

The only CI-specific detail is the **two-pass lint step** (blocking pass +
advisory pass for `SIM103`):

```yaml
- name: Lint Python with ruff
  run: ruff check . --ignore SIM103
- name: Lint advisories (non-blocking)
  run: ruff check . --select SIM103 || true

- name: Lint Cython
  run: cython-lint <pyx/pxd files> || true
```

The first two steps apply to all projects. The Lint Cython step
only applies to Cython projects.

The first ruff step fails the build on real errors. The second shows
`SIM103` (return-condition-directly) as informational — useful advice but
autofix-unsafe for multi-guard patterns. `cython-lint` runs non-blocking
due to a known false positive on relative cimports. See the
`project-setup` skill for the full rationale.

**Legacy flake8** config is not per-project. It is active at `~/.config/flake8`, which is a
symlink to `~/.spacemacs.d/flake8` — version-controlled and public at
[Technologicat/spacemacs.d](https://github.com/Technologicat/spacemacs.d/blob/master/flake8), which is the authoritative copy. Don't duplicate it into project-level files: per-project copies drift,
and a `.flake8` (or `setup.cfg`, or `tox.ini`) would be auto-discovered and silently
*override* the global. See the `project-setup` skill for the full story.

### GitHub Actions — Coverage (`.github/workflows/coverage.yml`)

- **Trigger:** push to the default branch only (not PRs)
- **Single Python version** — no matrix needed. **Use the newest the project supports**, i.e. the top of its CI matrix. That's the version most users will be on, and it's where new-syntax code paths actually run
  - **It needs bumping when the matrix grows**, and nothing will remind you — Dependabot updates actions, not this. Left alone, a `coverage.yml` freezes at whatever was newest the day it was written, which is exactly what happened across the fleet: before the 3.15 pass the coverage jobs sat at 3.10, 3.12, 3.13 and 3.14 with no rationale behind any of them. When you add a Python version to the CI matrix, bump the coverage job in the same commit — see the checklist below
  - **Version-gated code will look under-covered**, unavoidably. A single-version coverage run cannot exercise `if sys.version_info < (3, 12):` fallback branches. That's an artifact of the choice, not a defect to chase — running coverage across the whole matrix to fix it would cost far more than the signal is worth
- Uses `codecov/codecov-action`, SHA-pinned like every action
- Upload step:
  ```yaml
  - name: Upload coverage reports to Codecov
    uses: codecov/codecov-action@<sha>   # v6.x — resolve the SHA, see "Pin GitHub Actions to commit SHAs"
    with:
      token: ${{ secrets.CODECOV_TOKEN }}
  ```

### Adding a Python version to the matrix — the whole checklist

The matrix entry is the visible part, and on its own it is never the whole edit. Everything here
belongs in the same commit; each item was missed at least once during the 3.15 pass.

- **The matrix itself.** Add it to the Linux list. Leave the macOS/Windows `include:` entries on
  the newest *stable* version while the new one is at rc — those are spot-checks, and pinning them
  to a prerelease buys nothing. Say "newest stable" in the surrounding comment so the next reader
  knows it is deliberate.
- **`allow-prereleases: true`** on the `setup-python` step, for as long as the version is at
  alpha/beta/rc. The manifest marks prereleases unstable, so a bare `"3.15"` resolves to *nothing*
  without it — the job fails at setup, before any of your code runs. It is a no-op for versions
  that have a stable release, so it can stay until the cleanup pass.
- **The coverage job**, per the section above.
- **cibuildwheel's build list** (`[tool.cibuildwheel] build`, or `CIBW_BUILD`), for projects that
  publish wheels. Nothing adds a target implicitly — cibuildwheel builds what the selector names.
  Its *prerelease* gate is a separate thing and lags a version behind: as of 4.2.0 only `cp316*`
  needs `enable = ["cpython-prerelease"]`, so `cp315-*` is an ordinary target. Check
  `selector.py` in the installed cibuildwheel rather than guessing which version the gate is on.
- **The `Programming Language :: Python :: X.Y` classifier**, where the project lists them.
- **The `requires-python` cap**, where the project declares one. A capped project actively excludes
  the new version until the cap moves, and the exclusion propagates to everything depending on it.
- **The changelog entry and the version number.** It is a feature, so the release is a *minor* one —
  see "Settle the version number first" in the `release` skill for why the size of the diff is not
  the measure.

**Then check the third-party wheels before promising any of it.** A pure-Python project is
usually fine, but anything with a compiled dependency is gated on that dependency shipping wheels
for the new interpreter, and the two do not arrive together. One command settles it:

```bash
pip install --only-binary=:all: --dry-run scipy   # under the new interpreter
```

This is what blocked wlsqm on 3.15 while its two sibling Cython projects sailed through: it
`cimport`s `scipy.linalg.cython_lapack`, making SciPy a *build* dependency, and SciPy had no
`cp315` wheel. Note the asymmetry that makes this worth checking per project rather than per
fleet — NumPy had shipped `cp315` on day one, so pylu and pydgq were never blocked at all.

### Cython projects have no coverage job, deliberately

pylu, pydgq and python-wlsqm have CI but no `coverage.yml`, and that is a decision, not an oversight: measuring coverage of
compiled Cython requires building the extensions with line tracing enabled (`linetrace`
directive plus `CYTHON_TRACE`) and running coverage.py's Cython plugin — a separate build
configuration, maintained solely for the coverage run. For small numerical kernels the
signal doesn't repay the machinery. Don't "fix" the missing file.

### Coverage generation — pytest-cov vs coverage.py

**Note:** This section applies to projects using **pytest**. Two fleet projects don't — both
drive their tests through a top-level `runtests.py`, but for different reasons and in
different styles:

- **unpythonic** uses `unpythonic.test.fixtures`, its own macro-aware test framework (see
  the `testing-macro-enabled-python` skill).
- **mcpyrate** uses bare `assert`, and could not do otherwise. `unpythonic.test.fixtures`
  needs two things mcpyrate cannot supply: a *working macro expander* — which is precisely
  what mcpyrate is, and therefore what's under test, so the tests would presuppose their own
  subject — and a Common-Lisp-style conditions-and-restarts system, which is unpythonic's and
  well outside mcpyrate's remit (its only job is to be the expander). That's also why the
  framework lives in unpythonic rather than in mcpyrate.

Either way pytest-cov is not in play, so coverage is driven by coverage.py directly:

```yaml
- name: Generate coverage report
  run: |
    # `source` and `omit` come from [tool.coverage.run] in pyproject.toml.
    pdm run python -m coverage run -m runtests
    pdm run python -m coverage xml
```

Note `-m runtests` (module form), and **no `--source` flag** — the scoping belongs in
`[tool.coverage.run]`, where it also applies to local runs. A CLI `--source` *overrides* the
config rather than adding to it, so passing one silently discards the package scoping and
measures the whole tree.

**Gotcha:** if `pytest.ini` has `--cov=<package>` in `addopts`, then `coverage run -m pytest` conflicts with pytest-cov — `coverage xml` afterwards will say "No data was collected."

**Solution:** use pytest-cov to generate the XML directly:
```yaml
pytest tests/ -v --cov-branch --cov-report=xml:coverage.xml
```

- `--cov-branch`: branch coverage (recommended by codecov.io)
- `--cov-report=xml:coverage.xml`: XML for codecov upload
- `--cov=<package>` comes from `pytest.ini` addopts, no need to repeat

### `[tool.coverage.run]` — scope analysis to production code, exclude tests

Whichever runner you use, configure coverage to analyse production code only — not tests. Add to `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["<package>"]   # e.g. "unpythonic", "raven", "pyan"
omit = [
    "*/tests/*",         # or "*/test/*" — match the project's actual layout
]
```

**Path varies by project.** Most fleet projects use `test/` (singular) for the test directory; `unpythonic` uses `tests/` (plural) because `unpythonic.test` is reserved for the test *framework* module (`unpythonic.test.fixtures`). Pick the glob that matches your project's convention — and don't add the *other* one as a precaution: in `unpythonic`, `*/test/*` would mistakenly omit the framework, which *is* production code.

Three reasons to omit tests:

1. **Coverage signal is about production code.** A test file with 100% coverage just confirms the test ran — which the test runner already reports. It adds rows to the coverage XML without insight.
2. **Smaller coverage report**, easier to read on codecov.io.
3. **For projects whose macros are used only in tests, this also sidesteps a coverage.py parsing failure.** Coverage.py's report step (`coverage xml` / `coverage html`) parses each source file as standard Python to map line numbers. If a file uses a macro that rewrites the AST in a way that produces invalid surface Python (e.g. `nonlocal x` after `x = None`, which is legal once the `continuations` macro splits the body into separate functions but rejected by Python's parser as written), `coverage xml` fails with `Couldn't parse '...' as Python source`. Where such macros only appear in tests (as in `unpythonic` itself, which *implements* `continuations` but doesn't use it in its own production code), omitting tests sidesteps the parse step. Projects that use such macros in production code don't get a free fix from this — they need to either accept the unparseable file, mark it for `omit` directly, or migrate to a coverage tool that runs on bytecode rather than source.

The `omit` config applies even when the CLI uses `--source=.` (or any other override) — config-level omit is composed with whatever source is active.

### Codecov setup (one-time)

1. Sign in at [codecov.io](https://codecov.io/) with GitHub
2. Add the repository
3. Copy the upload token
4. Add as `CODECOV_TOKEN` in GitHub repo Settings → Secrets and variables → Actions

### README badges

```markdown
![100% Python](https://img.shields.io/github/languages/top/OWNER/REPO)
![supported language versions](https://img.shields.io/pypi/pyversions/PACKAGE)
![supported implementations](https://img.shields.io/pypi/implementation/PACKAGE)
![CI status](https://img.shields.io/github/actions/workflow/status/OWNER/REPO/tests.yml?branch=BRANCH)
[![codecov](https://codecov.io/gh/OWNER/REPO/branch/BRANCH/graph/badge.svg)](https://codecov.io/gh/OWNER/REPO)
![version on PyPI](https://img.shields.io/pypi/v/PACKAGE)
![PyPI package format](https://img.shields.io/pypi/format/PACKAGE)
![dependency status](https://img.shields.io/librariesio/github/OWNER/REPO)
![license](https://img.shields.io/pypi/l/PACKAGE)
![open issues](https://img.shields.io/github/issues/OWNER/REPO)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](http://makeapullrequest.com/)
```

#### Three namespaces

The local directory, the GitHub repo and the PyPI package are three different names, and all three can differ. Don't infer one from another:

| | local directory | GitHub repo | PyPI package |
|---|---|---|---|
| | `~/Documents/koodit/wlsqm` | `Technologicat/python-wlsqm` | `wlsqm` |
| | `~/Documents/koodit/pyan` | `Technologicat/pyan` | `pyan3` |
| | `~/Documents/koodit/raven` | `Technologicat/raven` | `raven-visualizer` |

So: `OWNER/REPO` comes from `git remote -v`, and `PACKAGE` comes from `name` in
`pyproject.toml` — never from the directory you happen to be sitting in. (Guessing is worse
than useless here: `raven` *is* a real PyPI package — Sentry's old client — so a wrong guess
resolves to somebody else's project instead of 404ing.)

`BRANCH` is the repo's default branch, which is *not* uniform across the fleet — see
"Default branch: `master` or `main`" above.

Badges referencing `PACKAGE` need a PyPI release. Most of the fleet has one; omit those
badges for the projects that don't (currently Raven, which is unpublished).

## Test dependencies in CI

**Don't use `[project.optional-dependencies].test`** (i.e. the `pip install -e .[test]` pattern). `[project.optional-dependencies]` is for published library features — optional runtime deps that a downstream user might opt into. `test` isn't a feature; it's dev plumbing. Nobody actually does `pip install pylu[test]` — it only exists so CI has something to install.

**Where the test deps live:** `[dependency-groups].dev`, always. How CI *gets* them depends on the pattern (see "How does CI install dependencies?" above) — a `pdm install` job picks them up from the dep group with nothing further to do; a raw-pip job has to name them, because pip cannot see dep groups.

For a raw-pip job, install them alongside the build deps: 

```yaml
- name: Install build and test dependencies
  run: pip install meson-python meson ninja Cython numpy pytest

- name: Install package
  run: pip install --no-build-isolation -e .
```

For pure-Python projects, drop the meson/ninja/Cython parts:

```yaml
- name: Install test dependencies
  run: pip install pytest

- name: Install package
  run: pip install -e .
```

For *why* CI installs this way rather than running `pdm install`, see "three environments,
three ways to install" at the top — the short version is that PEP 735 dep groups are
invisible to raw pip, *and* the CI environment is deliberately lighter than the dev one.

**In a raw-pip project, the CI list is hand-maintained, and that's its cost.** Adding a
test dep means adding it in two places — `[dependency-groups].dev` and the CI pip step —
with nothing enforcing the overlap. A test that imports something CI doesn't install fails
only in CI, on push. When adding a dependency to a test, check both. (A `pdm install`
project has no such hazard, which is a good reason to prefer it where the build system
allows.)

**Consolidation note:** don't duplicate the pytest version pin across `[project.optional-dependencies]` and `[dependency-groups].dev` — pick one. The canonical form has only `[dependency-groups].dev` with `pytest>=8.0`.

**Coverage variant:** if using pytest-cov, add `pytest-cov` to both the dev group and the CI install step. See "GitHub Actions — Coverage" for the coverage.yml setup.

### Dependabot

GitHub provides two Dependabot features:

**Security alerts** (automatic, no config needed):
- Enabled by default on public repos
- Scans `pyproject.toml` / `requirements.txt` / `setup.cfg` for known CVEs
- Files alerts in the Security tab; can auto-open PRs for fixes
- To enable on private repos: Settings → Code security and analysis → Dependabot alerts

**Version updates** (opt-in, needs config):
- We only auto-update GitHub Actions versions, not project dependencies
- Requires `.github/dependabot.yml`:
  ```yaml
  version: 2
  updates:
    - package-ecosystem: "github-actions"
      directory: "/"
      schedule:
        interval: "weekly"
  ```
- This keeps Action versions (checkout, setup-python, codecov) up to date automatically
- Dependabot understands SHA-pinned actions (see "Pin GitHub Actions to commit SHAs"): it bumps the pinned SHA **and** the trailing `# vX.Y.Z` comment together, so pinning does not freeze the actions — updates still arrive as reviewable PRs
- **Dependabot maintains pins; it does not create them.** Given a floating `uses: foo/bar@v6` it will keep the tag floating and only bump the major when one lands. It will never convert it into a SHA pin for you. So an unpinned workflow does not "get fixed on the next Dependabot run" — it stays unpinned indefinitely. Pinning is a one-time manual act per `uses:` line; Dependabot only takes over afterwards

### Pin GitHub Actions to commit SHAs (supply-chain hardening)

**Rule:** every `uses:` in every workflow pins a full 40-char commit SHA with a trailing `# vX.Y.Z` comment — never a floating tag (`@v6`) or branch (`@release/v1`). Scope is *everything*, including GitHub's own `actions/*` (matches OpenSSF Scorecard / GitHub's hardening guidance). Pin to the *latest* release of each action.

```yaml
- uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
```

**Why.** A tag or branch is a mutable ref: an attacker who compromises an action's repo or a maintainer account can silently repoint `@v6` at malicious code, and every workflow that floats on it runs that code on the next CI trigger — with whatever secrets the job holds. This is not hypothetical: `tj-actions/changed-files` was compromised exactly this way (March 2025). A commit SHA is immutable; it cannot be repointed.

**The version comment is load-bearing.** Dependabot reads `# vX.Y.Z` to know which version a SHA represents. If you hand-edit a pinned line, keep the comment in sync or Dependabot loses the version anchor.

**Resolve a tag/branch to its commit SHA** (deref annotated tags — pypa/* use them; GitHub `actions/*` are lightweight):

```bash
# tag (lightweight → commit directly; annotated → deref once more)
sha=$(gh api repos/OWNER/REPO/git/ref/tags/TAG -q '.object.sha')
[ "$(gh api repos/OWNER/REPO/git/ref/tags/TAG -q '.object.type')" = tag ] \
  && gh api repos/OWNER/REPO/git/tags/$sha -q '.object.sha' || echo "$sha"
# branch ref (e.g. gh-action-pypi-publish@release/v1)
gh api repos/OWNER/REPO/git/ref/heads/BRANCH -q '.object.sha'
# newest stable release tag for the comment
gh api repos/OWNER/REPO/releases/latest -q '.tag_name'
```

**Vet a bump before pinning it.** A green CI run proves the action *works*, not that it's *trustworthy* — and a legit publisher can still be a hijacked account. Check, in rough order of strength: (1) GPG-signed tag with *key continuity* — the same maintainer key signed the version you already trust and the new one (`gh api .../git/tags/SHA -q '.verification'`); a hijacker with token access can't forge the GPG signature. (2) Release cadence consistent with real development (multi-week RC cycle, many linked PRs — not a sudden lone release). (3) No open security advisories (`gh api repos/OWNER/REPO/security-advisories`). codecov-action and cibuildwheel were vetted this way before the fleet bump.

**Two limits on those checks, worth knowing before leaning on them:**

- **A tag-gated job means CI validates nothing about the action.** The `publish` job runs only on tags, so a `gh-action-pypi-publish` bump shows `publish: SKIPPED` on every PR run in this fleet. The green checkmark covers lint, tests and wheel builds; the action that was actually bumped never ran. Its first exercise is the next release you cut — so if a release misbehaves at upload time, a recently-bumped publish action is the first suspect. Every other pin (checkout, setup-python, cibuildwheel, codecov) does run on the PR, which is why this one is the exception to watch.
- **Not every action signs its tags, so check (1) is sometimes unavailable.** `pypa/gh-action-pypi-publish` uses GPG-signed annotated tags, and key continuity is checkable across versions. `pypa/cibuildwheel` does not sign at all — v4.1.1 is a lightweight tag pointing straight at an unsigned commit (verified 2026-08-03). When the strongest check is missing, fall back to (2) and (3) and say which check you *couldn't* run. Confirm it's the status quo and not a change: an action that signed the version you already trust and stopped signing the new one is a genuine signal, whereas one that never signed is just a weaker baseline.

Extracting the signing key id, when you need continuity rather than a bare `verified: true` (the API reports validity, not *which* key):

```bash
obj=$(gh api repos/OWNER/REPO/git/ref/tags/TAG -q '.object.sha')
gh api repos/OWNER/REPO/git/tags/$obj -q '.verification.signature' \
  | gpg --list-packets 2>/dev/null | grep -o 'keyid [0-9A-F]*' | head -1
```

**Once vetted, front-run Dependabot.** When you've already reviewed a bump and found it trustworthy, apply it across the fleet in one pass rather than waiting for each repo's weekly Dependabot slot.

Note this is *not* a security argument — with everything SHA-pinned there is no floating tag left to repoint, which is the whole point of pinning. The reasons are practical:

- **One review, nine repos.** You vetted the bump once; Dependabot would otherwise open the same PR nine times, at nine random moments over the following week, each wanting the same decision re-made.
- **Less notification noise.** Nine PRs firing on their own schedules, each on a different day and hour, is a week of inbox churn for a change already approved.
- **The fleet stays in step.** Same action, same SHA, everywhere — so "what version is X on?" has one answer rather than nine.

The one case where speed *is* security: a bump that fixes a known vulnerability in the action. There the exposure is the *old* pinned version, and applying the fix sooner shortens it — but that's about the flaw you're leaving behind, not about anything the new pin prevents.

Whole fleet was pinned this way on 2026-06-11; every default branch has zero floating refs. Each repo also needs `.github/dependabot.yml` (see "Dependabot") so the pins stay maintained.

### Least-privilege `GITHUB_TOKEN` permissions

**Rule:** every workflow declares a top-level `permissions:` block — `contents: read` for ordinary test/lint/build/coverage workflows. Put it right after `on:`, before `jobs:`:

```yaml
on:
  push:
    branches: [master]   # or [main] — check the repo; the brackets are YAML list syntax, keep them
  pull_request:
    branches: [master]   # or [main] — check the repo; the brackets are YAML list syntax, keep them

permissions:
  contents: read

jobs:
  ...
```

**Why.** Without an explicit block, every job inherits the repo-default token scope, which on older repos/orgs is **read-write**. A malicious dependency executing during `pip install` / build / test (on a push to the default branch, where the token is *not* auto-restricted) would then hold a write-capable `GITHUB_TOKEN` — enough to push commits, move tags, or cut a release. `contents: read` denies all of that. This is the blast-radius complement to SHA-pinning (see "Pin GitHub Actions to commit SHAs"): pinning stops untrusted code from running; this caps what it can do if it runs anyway. Fork-PR tokens are already forced read-only by GitHub, so this specifically closes the push-triggered path. Explicit-in-file beats the repo Settings → Actions → "read-only" toggle: it travels with the repo, is visible in review, and can't be silently flipped back in the UI.

**Jobs that need more declare it at the job level, which *replaces* the top-level default for that job** (unlisted scopes become `none` — not merged). The PyPI publish job is the standard case:

```yaml
  publish:
    permissions:
      id-token: write        # OIDC for trusted publishing; nothing else
    steps:
      - uses: pypa/gh-action-pypi-publish@<sha>       # v1.x
```

So the top-level `contents: read` covers test/build/sdist/coverage, and the publish job narrows itself to exactly `id-token: write`. A job that comments on PRs or pushes would add `pull-requests: write` / `contents: write` *at the job level only*. Fleet-wide as of 2026-06-12.

### Automated PyPI publishing (trusted publishers)

Publishes sdist + wheels to PyPI automatically when a version tag is pushed. Uses OpenID Connect — no API tokens needed.

> Every `uses:` in the examples is written as `@<sha>` with the intended version in a trailing comment. That is deliberate: **it will not run until you resolve the SHA**, which is the failure mode you want. A floating `@v6` copied out of a doc runs fine and stays unpinned forever — Dependabot maintains pins that already exist, it does *not* convert a floating tag into one. Resolve each with the recipe under "Pin GitHub Actions to commit SHAs".

**CI workflow addition** (add to the test/build workflow):

```yaml
on:
  push:
    branches: [master]   # or [main] — check the repo; the brackets are YAML list syntax, keep them
    tags: ["v*"]          # or ["*"] for bare-version tags — match the project's tag format
  pull_request:
    branches: [master]   # or [main] — check the repo; the brackets are YAML list syntax, keep them
  workflow_dispatch:

permissions:
  contents: read          # least-privilege default for all jobs

jobs:
  # ... existing test/build/sdist jobs ...

  publish:
    if: startsWith(github.ref, 'refs/tags/')  # adjust pattern for bare-version tags
    needs: [build, sdist]   # or whatever jobs produce the artifacts
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@<sha>        # v4.x
        with:
          path: dist/
          merge-multiple: true

      - uses: pypa/gh-action-pypi-publish@<sha>      # v1.x (branch ref upstream — pin it)
        with:
          packages-dir: dist/
```

**The `publish` job above is the same for every project.** What differs is the **build** job
that produces the artifacts it uploads, and there are two shapes:

- **Pure Python** — one job, `python -m build`, producing an sdist and a universal wheel.
- **Cython/meson-python** — a `cibuildwheel` matrix, producing a compiled wheel per platform
  and Python version. That's the heavy one: it needs the platform matrix, MSVC activation on
  Windows (see "Windows CI for Cython extensions"), and manylinux containers on Linux. See
  pylu's `ci.yml` for the full setup rather than reproducing it here.

The pure-Python build job:

```yaml
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>                 # v6.x
      - uses: actions/setup-python@<sha>             # v6.x
        with:
          python-version: "3.14"   # a currently-supported version; not a fixed recommendation
      - run: pip install build
      - run: python -m build
      - uses: actions/upload-artifact@<sha>          # v7.x
        with:
          name: dist
          path: dist/
```

**One-time setup per project:**

1. PyPI: go to `pypi.org/manage/project/PACKAGE/settings/publishing/` → Add publisher:
   - Owner: `Technologicat`, Repository: `REPO`, Workflow: `ci.yml`, Environment: `pypi`
2. GitHub: repo Settings → Environments → New environment → name it `pypi`
   - Optionally add protection rules (e.g. require approval before publishing)

### Windows CI for Cython extensions: force MSVC

**The gotcha.** GitHub Actions `windows-latest` runners ship with MinGW-w64
on the default PATH but NOT MSVC's `cl.exe` (MSVC Build Tools are
installed but only activated by `vcvarsall.bat` / a Developer Command
Prompt). If you build a Cython extension with `pip install --no-build-isolation -e .`
the way the test matrix does, meson's compiler auto-detection picks
whichever C compiler it finds first — MinGW-w64 gcc — and the resulting
`.pyd` files link against MinGW's runtime DLLs:

  - `libgcc_s_seh-1.dll` — MinGW's C runtime / SEH unwinding
  - `libgomp-1.dll` — MinGW's OpenMP runtime
  - `libstdc++-6.dll` — if any C++ shows up

These DLLs live in MinGW's `bin/` directory, NOT on the Python process's
DLL search path at import time. The user gets the very unhelpful
`ImportError: DLL load failed while importing <module>: The specified
module could not be found.` Linux and macOS both pass; only Windows
fails; no hint about *which* DLL is missing.

**The fix.** Activate the MSVC environment before the build on Windows
so that meson finds `cl.exe` first:

```yaml
- uses: ilammy/msvc-dev-cmd@<sha>   # v1.x
  if: runner.os == 'Windows'
```

**Add it to BOTH the `test` job AND the `build-wheels` job.** In the test job, place it
between `actions/setup-python` and the `pip install --no-build-isolation -e .` step. In the
build-wheels job, place it before the `pypa/cibuildwheel` step.

**cibuildwheel does not activate MSVC for you** — a natural thing to assume, and false.
Setuptools/distutils projects get MSVC auto-detection from distutils itself (its
"python-was-built-with-MSVC" logic), but meson-python uses meson's own compiler discovery,
which takes whichever compiler comes first on the runner's PATH. On GitHub Actions Windows
runners that is Strawberry Perl's bundled MinGW-w64 gcc (`C:\Strawberry\c\bin`).

So without the step, the wheel builds against MinGW's `libgomp`/`libgcc_s_seh`, and then
fails at import — inside cibuildwheel's own test phase — with the same "DLL load failed"
error described above.

**The trigger is OpenMP, so a green Windows job does not mean the step is unnecessary.**
A MinGW build of plain C kernels links nothing beyond the UCRT and `python3XX.dll`, imports
fine, and passes every test — which is why pylu and pydgq ran for months without the step
while wlsqm needed it from the start (verified 2026-08-14: all three built with
`C:\Strawberry\c\bin` gcc 15.2.0; only wlsqm compiles OpenMP). The diagnostic is
`delvewheel`'s line in the repair phase — cibuildwheel runs it by default on Windows:
`no external dependencies are needed` means the current sources happen not to need MinGW's
runtime, **not** that the toolchain is right. Add the step anyway. Otherwise the day someone
compiles a `prange`, Windows breaks with a bare "DLL load failed" naming neither the missing
library nor the commit that caused it — and the workflow, untouched for months, is nobody's
first suspect.

MSVC-built `.pyd` files link only against the universal CRT
(`api-ms-win-crt-*.dll`, always present on Windows 10+) and `vcomp140.dll`
(MSVC's OpenMP runtime, shipped with every Python-for-Windows install),
both of which are always on the DLL search path for a 64-bit Python
process.

scipy and numpy use the same `ilammy/msvc-dev-cmd` approach in both
their test and wheel-build jobs on Windows.

**Diagnostic recipe** (for when the symptom is `ImportError: DLL load
failed` on Windows and you don't know which DLL is missing). Add this as
a temporary step to the Windows test job under `shell: bash` (Git Bash is
installed by default on GitHub Actions Windows runners; PowerShell won't
parse Python heredocs):

```yaml
- name: Diagnose .pyd DLL dependencies (Windows)
  if: runner.os == 'Windows'
  shell: bash
  run: |
    python -m pip install -q pefile
    python - <<'PY'
    import ctypes, glob, os
    import pefile
    # meson-python editable install puts .pyd files under build/<tag>/...
    pyds = sorted(glob.glob('build/**/*.pyd', recursive=True))
    for p in pyds:
        pe = pefile.PE(p, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
        imports = [e.dll.decode(errors='replace') for e in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', [])]
        print(f'{p}:'); [print(f'  {n}') for n in imports]
        pe.close()
    for p in pyds:
        try:
            ctypes.WinDLL(os.path.abspath(p))
            print(f'WinDLL OK  : {p}')
        except OSError as e:
            print(f'WinDLL FAIL: {p} -- {e}')
    PY
  continue-on-error: true
```

Signs that the MSVC fix is what you need:

- `libgcc_s_seh-1.dll` or `libgomp-1.dll` or `libstdc++-6.dll` appear in
  the pefile import table of any `.pyd`.
- `ctypes.WinDLL` fails on exactly the `.pyd` files that import one of
  those MinGW DLLs.

Expected pefile import table after the MSVC fix (no libgcc/libgomp/libstdc++):

```
KERNEL32.dll
api-ms-win-crt-heap-l1-1-0.dll
api-ms-win-crt-runtime-l1-1-0.dll
api-ms-win-crt-stdio-l1-1-0.dll
api-ms-win-crt-string-l1-1-0.dll
api-ms-win-crt-math-l1-1-0.dll     (only for math-heavy modules)
python3XX.dll
vcomp140.dll                       (only for OpenMP-using modules)
```

Remove the diagnostic step once the fix is confirmed.

## Workflow filter globs are a hybrid syntax, and `*` is the glob one

`branches:`, `tags:` and `paths:` filters look like shell globs but are not quite, and the mixture is
the trap. From GitHub's [filter pattern cheat sheet](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#filter-pattern-cheat-sheet):

- `*` — zero or more of **any** character, except `/`. A glob star: it does not attach to whatever
  precedes it.
- `?` — zero or one of the **preceding** character.
- `+` — one or more of the **preceding** character.
- `[]` — one alphanumeric character from the listed set or range, ranges limited to `a-z`, `A-Z`,
  `0-9`. `[1-2]00` matches `100` and `200`.
- `!` — negates earlier positive patterns, but only as the first character.

So `?` and `+` are Kleene operators on one character while `*` is not, which is why `[0-9]*` reads
correctly as "a digit, then anything" and `v1.*` matches `v1.0` rather than only `v1.` repeated.

**YAML quoting is load-bearing here.** A pattern starting with `*`, `[` or `!`, or containing `[`/`]`
inside a flow sequence, must be quoted — unquoted it is a YAML parse error and the workflow does not
run at all.

Why it matters beyond pedantry: a tag filter is what stands between an ordinary tag and a PyPI
release, and getting it wrong fails in whichever direction is worse. Too loose and a scratch tag
publishes; too tight and a real release tag never fires, which is the case the `release` skill warns
costs either a force-moved public tag or a burnt version number.

## What varies per project — check, don't assume

Nothing in this fleet is uniform. Every item below differs between projects, and each one
fails *quietly* when guessed wrong. Look it up in the repo; the linked sections say how.

| Check | Why it bites |
|---|---|
| **How CI installs deps** — `pdm install`, raw pip + build deps, or a hand-picked subset | See "How does CI install dependencies?". Getting this wrong means a job that can't build, or a second dep list nobody knew existed |
| **Default branch** — `master` or `main` | See "Default branch: `master` or `main`". A wrong branch means a workflow that never triggers and badges that read "unknown" — no error either way |
| **Test runner** — pytest, or a `runtests.py` driving `unpythonic.test.fixtures` (unpythonic) or bare asserts (mcpyrate) | Determines whether coverage runs through pytest-cov or coverage.py directly. See "Coverage generation" |
| **Coverage job's Python version** — should be the newest the project supports | See "GitHub Actions — Coverage". Left alone it freezes at whatever was current when the file was written |
| **Whether there's a coverage job at all** — Cython projects deliberately have none | See "Cython projects have no coverage job, deliberately". Don't "fix" the absence |
| **The three names** — local directory, GitHub repo, PyPI package | See "Three namespaces". Guessing resolves to *someone else's* project rather than failing |
| **Tag format** — `vX.Y.Z` or bare `X.Y.Z` | See the `release` skill. A tag in the wrong format won't fire the publish workflow |
| **Action versions** | Don't copy any version number out of this file — resolve the current release and pin its SHA. See "Pin GitHub Actions to commit SHAs" |
| **pytest-cov in `addopts`** | Conflicts with `coverage run -m pytest`. See the gotcha under "Coverage generation" |
