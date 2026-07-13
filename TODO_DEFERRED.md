# Deferred TODOs

## CI does not catch continuation-indent formatting (we ship broken formatting)

**Priority: sooner rather than later.** Formatting-broken commits are reaching the
default branch, because ruff — the only linter CI runs — cannot see the problem.

Demonstration:

```python
result = some_function(arg_one,
    arg_two)                        # E128, continuation line under-indented
```

`ruff check --select E` reports **"All checks passed!"** on that file.

**The plan recorded in the `project-setup` skill is not achievable as written.** It
says a future pass should "re-enable E128 and similar continuation-indent rules"
in ruff. Ruff has no such rules: as of 0.15.6 it implements `E101` and `E111`–`E117`
(and the latter are preview-gated), and the entire `E12x` continuation-line family
is simply absent — not disabled, not preview, not there. flake8/pycodestyle caught
these; ruff never ported them, treating them as the formatter's job.

The hard constraint: **no auto-rewriting.** `ruff format` is Black-shaped and would
reformat the fleet against the house style, which is not acceptable. We want a
*check*, not a rewriter.

Both viable options were tested on the sample above (2026-07-13). Neither rewrites
the file:

1. **`pycodestyle --select E12`** — the recommended gate. Output is standard linter
   form (`file:2:5: E128 continuation line under-indented for visual indent`), exit 1.
   It is a checker, not a fixer, so it cannot rewrite anything even by accident.
2. **`autopep8 --select E12 --diff --exit-code`** — prints the corrective diff and
   exits 2. Better as the *local fix* companion (drop `--diff`, add `--in-place`)
   than as the CI gate, since a diff is noisier to read in a CI log than a line
   number.
3. `ruff format --check` — **rejected.** Check-only, yes, but it enforces Black's
   entire style, not just continuation indents, and would fight the house style
   everywhere.

So: `pycodestyle --select E12` as a blocking CI step alongside ruff; `autopep8
--select E12 --in-place` as the fix. Cost is a second linter in CI, which is the
price of ruff not having ported these rules.

Both tools are already installed (`~/.local/bin`) and autopep8 is already in the
dev-dependency baseline, so this is a CI-config change, not a new dependency.

Whatever is chosen goes into the two-pass lint step in `ci-setup` and the canonical
config in `project-setup`, and the skill's "Deferred: ruff formatting checks"
paragraph gets replaced with what was actually done.

Discovered during the `~/.claude` cloudification (2026-07-13).

## Three projects disagree with the lockfile policy

The policy (in the `project-setup` skill): libraries don't commit `pdm.lock`, apps
do, dual-use library+CLI projects count as apps.

Checked 2026-07-13 with `git ls-files pdm.lock` across the fleet. Three projects
don't match, and the stale classification list in the skill — since removed — had
been papering over it:

- **pylu** — a library, but *commits* `pdm.lock`.
- **raven** — an app, but gitignores it.
- **arxiv-api-search** — dual-use, so app-like by the policy, but gitignores it.

(chandra commits, and is app/dual-use-ish, so it's consistent — it was simply never
listed.)

Either the repos are out of compliance, or the policy has quietly changed and the
skill records an intent nobody follows. Worth deciding which, rather than leaving
the two in contradiction. Raven is the interesting one: it's the actual deployed
app, and it's the one *without* a reproducible-build lockfile.

Discovered during the `~/.claude` cloudification (2026-07-13).

## Add an internal-reference check to fleet CI

Fleet CI runs `ruff`, `cython-lint` and `pytest` — Python only. Nothing checks that
the *docs* still refer to things that exist. This session found several instances of
exactly that rot: a docstring in Raven giving a module path that no longer imports
(`raven.common.tests.lanczos_visual_test`, missing the `image` component), and, in
this repo before the cutover, cross-references to notes files that had been converted
into skills.

Wanted: a check that relative Markdown links resolve, and that file paths named in
docs and docstrings exist. Offline and deterministic — no network, so it can be
blocking without ever going red for reasons unrelated to the commit. That property is
the whole point; an external link checker on push would fail on rate limits and 403s
from CI runners, and a CI that cries wolf trains you to ignore it.

Design question to settle first: nine repos need this, and nine copies of a script
will drift. Options are a copy per repo (simple, drifts), a second SHA-pinned checkout
of this repo in each workflow (DRY, adds a cross-repo dependency), or a small reusable
composite action. Decide before rolling out.

Explicitly *not* in scope, having been considered and declined for now: external link
checking (worth doing eventually, but on a schedule rather than on push), and
`codespell`.

Note the limit of any of this. The failures that actually bit during the cutover —
CRT shader parameters a full edit behind reality, a benchmark run in the wrong venv, a
rationale that was fluent and wrong — are claims that drifted from the world, and no
linter checks a claim against reality. Machine checks buy the easy half.

Discovered during the `~/.claude` cloudification (2026-07-13).
