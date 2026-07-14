# Deferred TODOs

## Coverage jobs are running stale Python versions

Now that the `ci-setup` skill says the coverage job should run the *newest* Python the
project supports, the fleet can be measured against it — and most of it is behind. Each
`coverage.yml` froze at whatever was newest the day it was written, and nothing ever
prompted a bump.

Checked 2026-07-14:

| project | coverage runs | CI matrix tops out at |
|---|---|---|
| mcpyrate | **3.10** | 3.14 |
| unpythonic | **3.12** | 3.14 |
| chandra | **3.13** | 3.14 |
| pyan | 3.14 | 3.14 — correct |
| raven | 3.12 | 3.12 — correct (its cap) |

Mechanical fix: bump the three, in one commit each. Worth doing not because the coverage
number changes much, but because a coverage job on 3.10 never exercises the newest-syntax
paths — which is where new code lives.

(pylu, pydgq and python-wlsqm have no coverage job at all. That is deliberate — Cython
coverage needs a line-traced build and coverage.py's plugin, judged not worth it during
their modernization — and is now recorded in the `ci-setup` skill so nobody "fixes" it.)

Discovered during the `~/.claude` cloudification (2026-07-14).

## Evaluate pyan's extra ruff rules for the rest of the fleet

pyan selects `E, W, F, I, B, C4, UP, ARG, SIM`; raven, unpythonic, mcpyrate and chandra
select only `E, W, F, SIM`. So `I` (isort), `B` (bugbear), `C4` (comprehensions), `UP`
(pyupgrade) and `ARG` (unused arguments) are enforced in exactly one project.

The divergence is provenance, not design: pyan has always been its own thing, with more
community involvement than the rest of the fleet. **pyan keeps its config** — this item
is only about whether any of those rules would earn their place elsewhere.

The one measurement taken so far: enabling `I` on raven reports **211 violations**. Raven's
imports are grouped thematically (stdlib, then dependencies, then local) and alphabetised
*within* each group — which is isort's own model, so the count is surprising and worth
understanding before drawing a conclusion. It may be the `import x` / `from x import y`
interleaving rule, or the section boundaries not being where isort infers them.

The question to answer for each rule, per the house line that linters are advisors and
working code shouldn't be rewritten to satisfy one: **does it maintain the house style, or
fight it?** `I` in particular could go either way — it might codify the existing import
discipline, or it might flatten deliberate thematic grouping. Look at what the autofix
actually does to a few real files before deciding.

Discovered during the `~/.claude` cloudification (2026-07-14).

## Design a study: does CLAUDE.md rule count degrade rule-following?

`CLAUDE.md` currently holds ~66 top-level bullets and 9 sub-rules; discounting the
project list (reference data, not rules) that is roughly **56 behavioural rules**, and
that undercounts — several sections state rules in prose rather than bullets. Folklore
in the wild (a blog post neither of us can now cite, hence worth exactly what that is)
puts the point where frontier models start silently dropping rules at around 50. We
are in that zone, on a hunch, with no measurements.

**Two hypotheses that predict different fixes, and which we have been conflating:**

- **Dilution** — too many independently-firing rules; attention doesn't stretch. Fix:
  cut or demote rules.
- **Shape** — individual rules are phrased so as to defeat themselves, or to require
  judgment they don't supply. Fix: rewrite the rule; cutting good rules would be
  actively harmful.

Today produced one data point *against* naive dilution: the deadpan rule is prominent,
not buried, and was violated repeatedly — and its cause turned out to be self-defeating
phrasing (naming the register puts the word in the model's mouth). Wrong fix under the
dilution hypothesis, right fix under the shape hypothesis.

**What to measure** (instrument: `cc-log-extract` over `~/.claude/projects/*/*.jsonl`,
which stamps every turn with the model that produced it):

- **Dead rules** — which rules have never been applicable in any session? Pure cost;
  prune candidates.
- **Resident-but-violated** — which rules were broken while sitting in context? Shape
  problems, not dilution. Deadpan is the known case; find the others.
- **Fixed-only-when-reminded** — rules followed only after the user restates them
  mid-session. *This* is the dilution signal, and the one that would justify cutting.
- **Rate, not count**, and split by model era (4.6 / 4.7 / 4.8), since the logs span the
  upgrades.

**Fold in the other open question** (same instrument, same logs): does the rate of
*confabulated rationale* — unprompted "because…" / "therefore…" that was never checked —
differ across model versions, or did it only become visible because the work shifted to
rationale-dense documentation? Classify claims as verified-in-session vs asserted, and
compare rates rather than counts, since the docs-heavy period inflates the denominator.

Both questions want a separate session with a clear head; the value is in the *design*,
not in a quick grep. Confounds to control: task type shifted over the period, rules were
added at different times (a rule added in July can't be violated in April), and position
in the file may matter independently of count.

Discovered during the `~/.claude` cloudification (2026-07-13).

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

**Select `E128`, not the whole `E12` family.** The house style *deliberately ignores*
two continuation rules — the global flake8 config ignores `E126` (overhanging indent)
and `E127` (continuation line over-indented). Verified 2026-07-13: `pycodestyle
--select E12` fires `E127` on code the house style intentionally permits, so a blanket
`E12` gate would fight the very style it exists to protect. `--select E128` flags only
the under-indent, which is the actual bug. If more of the family is ever wanted, add
codes individually (`E122`, `E125`, `E131`) — never `E126`/`E127`.

Both viable options were tested on the sample above (2026-07-13). Neither rewrites
the file:

1. **`pycodestyle --select E128`** — the recommended gate. Output is standard linter
   form (`file:2:5: E128 continuation line under-indented for visual indent`), exit 1.
   It is a checker, not a fixer, so it cannot rewrite anything even by accident.
2. **`autopep8 --select E128 --diff --exit-code`** — prints the corrective diff and
   exits 2. Better as the *local fix* companion (drop `--diff`, add `--in-place`)
   than as the CI gate, since a diff is noisier to read in a CI log than a line
   number.
3. `ruff format --check` — **rejected.** Check-only, yes, but it enforces Black's
   entire style, not just continuation indents, and would fight the house style
   everywhere.

So: `pycodestyle --select E128` as a blocking CI step alongside ruff; `autopep8
--select E128 --in-place` as the fix. Cost is a second linter in CI, which is the
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
