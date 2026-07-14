---
name: ci-setup
description: Reference for setting up or modernizing CI for a Python project in the fleet — GitHub Actions, test matrix, pytest coverage and Codecov, cibuildwheel for Cython extensions, Windows MSVC activation, automated PyPI publishing via trusted publishers, and supply-chain hardening (pinning actions to commit SHAs, least-privilege GITHUB_TOKEN permissions, vetting action bumps). Use when configuring CI workflows, adding coverage, fixing CI failures, hardening CI / pinning actions to SHAs / setting workflow token permissions, or scaffolding a new project's CI.
---

# CI/Coverage setup

Reference for CI/coverage setup across projects.

Sibling skill: `project-setup` covers the build system and linter config.

## Components

### GitHub Actions — Test matrix (`.github/workflows/ci.yml`)

- **Trigger:** push + PR to the repo's **default branch**, and workflow_dispatch. That branch is not the same across the fleet — see "Default branch: `master` or `main`" below
- **Matrix:** all supported Python versions, `fail-fast: false`
- **Steps:** checkout → setup-python → install deps → ruff lint → pytest
- Use `actions/checkout` and `actions/setup-python` (v6 as of Apr 2026) — **SHA-pinned** (see "Pin GitHub Actions to commit SHAs"), like every action
- **Top-level `permissions: contents: read`** (after `on:`, before `jobs:`) — least-privilege `GITHUB_TOKEN` (see "Least-privilege `GITHUB_TOKEN` permissions")
- For pre-release Python versions (e.g. 3.15): `allow-prereleases: true`
- **Install pytest as a raw pip step alongside the other build/test deps** (see "Test dependencies in CI" below). Don't use `[project.optional-dependencies].test` — pytest is dev tooling, not a published library feature.
- Install ruff and cython-lint separately in the lint job — they're CI tools, not project test deps. (They also live in `[dependency-groups].dev` so local dev has them.)
- **Cython extensions on Windows:** add an `ilammy/msvc-dev-cmd` step (SHA-pinned, like every action) before the build step, conditional on `runner.os == 'Windows'`. Without it, meson picks up MinGW-w64 gcc and the resulting `.pyd` files link to DLLs that aren't on the runtime search path. See "Windows CI for Cython extensions: force MSVC" below for the full story.

### Default branch: `master` or `main`

**The fleet is split, so don't assume.** The older projects are on `master`; the ones
started later are on `main`. Getting this wrong means workflows that never trigger and
badges that render as "unknown" — both of which fail *quietly*.

```bash
git symbolic-ref --short HEAD          # in a clean checkout of the default branch
gh repo view --json defaultBranchRef -q .defaultBranchRef.name    # authoritative
```

Prefer the `gh` form: a local checkout can be on a feature branch, or stale. (While
you're at it, note that the *directory* name is not the repo name either —
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

**Legacy flake8** config is not per-project — it lives globally at
`~/.config/flake8`. Don't duplicate it into project-level files.

### GitHub Actions — Coverage (`.github/workflows/coverage.yml`)

- **Trigger:** push to the default branch only (not PRs)
- **Single Python version** (e.g. 3.12) — no matrix needed
- Uses `codecov/codecov-action`, SHA-pinned like every action
- Upload step:
  ```yaml
  - name: Upload coverage reports to Codecov
    uses: codecov/codecov-action@<sha>   # v6.x — resolve the SHA, see "Pin GitHub Actions to commit SHAs"
    with:
      token: ${{ secrets.CODECOV_TOKEN }}
  ```

### Coverage generation — pytest-cov vs coverage.py

**Note:** This section applies to projects using pytest. Projects with custom test runners (e.g. `runtests.py` with bare asserts or a custom test framework) will need a different approach — likely `coverage run runtests.py` followed by `coverage xml`.

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

Note: `OWNER/REPO` is the GitHub path (e.g. `Technologicat/pyan`), `PACKAGE` is the PyPI name (e.g. `pyan3`) — these may differ, and the directory name may differ from both (`~/Documents/koodit/wlsqm` is `Technologicat/python-wlsqm`; check `git remote -v`). `BRANCH` is the repo's default branch, which is *not* uniform across the fleet — see below. Badges referencing `PACKAGE` require a PyPI release; omit them for GitHub-only projects.

## Test dependencies in CI

**Don't use `[project.optional-dependencies].test`** (i.e. the `pip install -e .[test]` pattern). `[project.optional-dependencies]` is for published library features — optional runtime deps that a downstream user might opt into. `test` isn't a feature; it's dev plumbing. Nobody actually does `pip install pylu[test]` — it only exists so CI has something to install.

**Canonical pattern:** put `pytest` (and any other test deps like `pytest-cov`, `coverage`) in `[dependency-groups].dev` for local dev, and install them as a raw pip step in CI alongside the other build deps:

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

PEP 735 `[dependency-groups]` aren't installable via raw `pip`; they're only visible to tools like PDM and uv. That's why CI uses a separate raw-pip step. (Local dev uses `pdm install` which reads the dep groups directly.)

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

**Once vetted, front-run Dependabot.** When a bump is already reviewed-trustworthy, apply it fleet-wide rather than waiting for each repo's weekly Dependabot slot to fire — less wall-clock window where a floating tag could be repointed.

Whole fleet was pinned this way on 2026-06-11; every default branch has zero floating refs. Each repo also needs `.github/dependabot.yml` (see "Dependabot") so the pins stay maintained.

### Least-privilege `GITHUB_TOKEN` permissions

**Rule:** every workflow declares a top-level `permissions:` block — `contents: read` for ordinary test/lint/build/coverage workflows. Put it right after `on:`, before `jobs:`:

```yaml
on:
  push:
    branches: [DEFAULT-BRANCH]   # master or main — check the repo
  pull_request:
    branches: [DEFAULT-BRANCH]   # master or main — check the repo

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
    branches: [DEFAULT-BRANCH]   # master or main — check the repo
    tags: ["v*"]          # or ["*"] for bare-version tags — match the project's tag format
  pull_request:
    branches: [DEFAULT-BRANCH]   # master or main — check the repo
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

**For pure Python projects** (no cibuildwheel), the build job is simpler:

```yaml
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>                 # v6.x
      - uses: actions/setup-python@<sha>             # v6.x
        with:
          python-version: "3.14"
      - run: pip install build
      - run: python -m build
      - uses: actions/upload-artifact@<sha>          # v7.x
        with:
          name: dist
          path: dist/
```

**For Cython projects**, use cibuildwheel (see pylu's `ci.yml` for the full setup with platform matrix).

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

**Add it to BOTH the `test` job AND the `build-wheels` job.** In the
test job, place it between `actions/setup-python` and the
`pip install --no-build-isolation -e .` step. In the build-wheels job,
place it before the `pypa/cibuildwheel` step. Contrary to initial
assumption, cibuildwheel does NOT automatically activate MSVC for
meson-python builds — distutils/setuptools based projects get MSVC
auto-detection from distutils itself (via its "python-was-built-with-
MSVC" logic), but meson-python uses meson's own compiler discovery,
which picks up whichever compiler is first on the runner PATH. On
GitHub Actions Windows runners that's Strawberry Perl's bundled
MinGW-w64 gcc (`C:\Strawberry\c\bin`) — so without the step, the
wheel build links against MinGW's libgomp/libgcc_s_seh and the
resulting wheel fails at import time in cibuildwheel's own test phase
with the same "DLL load failed" error.

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

## Project-Specific Considerations

When setting up CI for a project, check:

- **Build system**: in CI, always install test deps (`pytest`, etc.) as a separate raw-pip step and the project itself with plain `pip install -e .` (or `pip install --no-build-isolation -e .` for meson-python projects). Don't use `[test]` extras — see "Test dependencies in CI" above.
- **Test runner**: Some projects use pytest, some have a custom runner (`runtests.py`). Adjust CI steps accordingly.
- **Action versions**: the usual set is `actions/checkout`, `actions/setup-python`, `codecov/codecov-action`, `actions/upload-artifact`, `actions/download-artifact`. Don't copy version numbers out of this file — they go stale. Resolve the current release of each and pin its SHA (see "Pin GitHub Actions to commit SHAs" for the `gh api` one-liners); Dependabot maintains the pins from there.
- **pytest-cov conflict**: Check if `pytest.ini` / `pyproject.toml` has pytest-cov in addopts (see the gotcha under "Coverage generation").
