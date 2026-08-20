# Deferred TODOs

## Fork `humanizer` and tune it to this fleet's writing

*Cluster: prose · Cost: M · Gate: none · Filed: 2026-08-19 · See also: `scripts/check-prose.py`*

[`blader/humanizer`](https://github.com/blader/humanizer) is a Claude Code skill that rewrites AI-sounding
prose, two passes against 35 Wikipedia-derived patterns. Juha wants one matched to his own style
(2026-08-19). **Off the shelf it would fight the house style**: it flags em dashes, which `CLAUDE.md`
mandates, and it targets "not X, it's Y", which the measurement below says is not this model's habit at all.

What a fork should be tuned against, measured 2026-08-19, `rather than` per 1000 words:

| hand-written | | agent era | |
|---|---|---|---|
| pylu | 0.00 | `raven/common/gui` | 1.50 |
| wlsqm | 0.02 | `raven/.../fdialog.py` | 3.78 |
| pydgq | 0.03 | | |
| extrafeathers | 0.03 | | |
| randomthought | 0.06 | | |
| unpythonic | 0.08 | | |
| mcpyrate | 0.11 | | |

Seven hand-written corpora, some 590k words across numerics, FEM, ML and macro tooling, land between 0.00
and 0.11. Agent-written code sits fourteen to seventy-five times higher.

Two markers that look like the same problem and are not. `instead of` runs at 0.12–0.54 on *both* sides, so
it is ordinary English. "not X, it's Y" runs 0.05–0.07 hand-written and 0.00–0.06 agent-era — a human's
occasional construction here, and Juha's read is that it belongs to GPT and Qwen (he uses neither for prose;
Qwen's contributions to Raven are small and much rewritten since — see `AUTHORS.md`). So essentially the
entire anomaly is **one phrase**, and a general list of AI tells would bury it among thirty-four others.

`scripts/check-prose.py` already does the measuring half, and deliberately does not rewrite. The fork would
be the rewriting half, and the same finding should discipline it: a general list of AI tells buries a
specific habit that a single number exposes.

## Survey `unpythonic.syntax`'s docstrings against the "what belongs in a docstring" list

*Cluster: docstring-rules · Cost: S · Gate: none · Filed: 2026-08-19*

The docstring rule in `CLAUDE.md` now says a docstring holds arguments, return value and which cases are
handled, and that a second paragraph outside those three is a comment in the wrong place. That list was
written from ordinary function docstrings.

**`unpythonic`, and `unpythonic.syntax` especially, carries docstring material that plainly belongs to the
caller and fits none of the three** (Juha, 2026-08-19). What that material *is* has not been characterized —
naming it is the work here, and guessing at it in advance is how the list would acquire a category nobody
needed.

So: read those docstrings, name the categories actually present, and either widen the list or state why the
macro layer is a genuine exception. Until then the three-item list should be read as provisional rather than
as exhaustive, and a docstring that seems to need something else is evidence for this item rather than a
violation.

## Add `~/.spacemacs.d` to the fleet, after the personal machine's reinstall

`Technologicat/spacemacs.d` is checked out at `~/.spacemacs.d` on both machines and
belongs in the project list on the same reasoning that put `dotclaude` there: config
that lives outside `~/Documents/koodit`, is on GitHub, and silently drifts between
machines.

**Blocked, and the block is the point.** The repo has moved on for the work machine's
newer Emacs/Spacemacs; the personal machine is still on the older pair, with a locally
modified `init.el` (its HEAD is at `fa49f14`, 2026-04-11). Adding it to the table now
would mean the next `fleet-pull.sh` run on the personal machine pulls config written
for software that is not installed there — and the stash-pop would put the local
`init.el` edits straight into the collision path. So: not until the personal machine's
OS upgrade, which is planned as a full reinstall and cleanup.

When that lands, the change is three lines: an entry under **Harness (not code)** in
`CLAUDE.md`, a row in the `PROJECTS` table in `scripts/fleet-pull.sh` carrying the
explicit path `$HOME/.spacemacs.d`, and an alternation for it in the CLAUDE.md
cross-check regex in `check_project_list` (which currently matches only the `koodit`
paths and `~/.claude`).

Noticed while adding dotclaude to the fleet (2026-08-03).

## Python 3.15: a cleanup pass once it goes final

**The support pass is done and released, 2026-08-18.** Every project that can take 3.15 has it,
and everything that ships to PyPI has shipped:

| release | what it was |
|---|---|
| `pyan` 2.7.0 *Triangulation* | `DictComp.value` now optional; `symtable` renamed its anonymous scopes |
| `mcpyrate` 4.3.0 *Weigh anchor* | could not import at all — loader-protocol signature |
| `unpythonic` 2.4.0 *'Tis but a scratch* | macros unchanged; the work was property-checking tests |
| `pylu` 1.1.0, `pydgq` 1.1.0 | CI matrix + `cp315-*` wheels, no source changes |
| `chandra` 0.3.0 *First light* | CI matrix + coverage, no source changes |

arxiv-api-search got 3.15 in CI but is not released (retired; see `CLAUDE.md`). Briefs are archived
at `briefs/done/python-3.15-support.md` in each of the three AST-user repos.

**python-wlsqm is the one project still without it**, blocked on SciPy, which has no `cp315` wheel
and is a *build* dependency there (`cimport scipy.linalg.cython_lapack`). Tracked in wlsqm's own
`TODO_DEFERRED.md`, with the one-command check that will say when it clears; expect that some weeks
after 3.15 final.

**What remains is a cleanup pass, gated on 3.15 going final:**

- Drop `allow-prereleases: true` from every `setup-python` step that has it — it is a no-op by
  then, but it is also a lie about the version's status. Currently in pylu, pydgq, chandra,
  arxiv-api-search, mcpyrate, unpythonic and pyan, in both `ci.yml` and `coverage.yml`.
- Move the macOS/Windows `include:` entries from 3.14 to 3.15 (they deliberately track the newest
  *stable* version, so they lag while a version is at rc).
- Do wlsqm, if SciPy has caught up by then.

All three prerequisites are other people's release schedules — CPython 3.15 final, a ruff that can
parse PEP 798 (the item below), and SciPy's `cp315` wheels. Nothing here is actionable before those
land, so this is a wait rather than a queue.

Two questions this pass raised, both since resolved, recorded so they are not re-asked:

- **Which fleet projects declare an unbounded `requires-python` floor?** pylu, pydgq, wlsqm,
  chandra and arxiv-api-search. None of them can hit the resolver trap that made this worth
  asking — that trap needs a *capped* dependency, and the only capped packages in the fleet are
  mcpyrate and unpythonic, whose only fleet-internal dependents (unpythonic itself, and Raven at
  `<3.13`) are capped already.
- **Does cibuildwheel need `enable = ["cpython-prerelease"]` for cp315?** No. As of 4.2.0 its gate
  matches `cp316*` — the gate tracks the *next* version, not the newest one.

Raised while merging the cibuildwheel 4.2.0 Dependabot PRs (2026-08-14).

## Sweep the ruff excludes once ruff supports PEP 798

ruff 0.15.10 cannot *parse* comprehension unpacking — it reports `invalid-syntax: Iterable
unpacking cannot be used in a comprehension` — and a syntax error cannot be suppressed with
`# noqa`. So every 3.15 test fixture needs its directory excluded in `[tool.ruff]`. `pyan` has
`tests/test_code_315` excluded with a comment saying to retry dropping it; `mcpyrate` and
`unpythonic` will need the same when their 3.15 fixtures land.

The excludes hide real lint from those files while they exist, so they are worth actually removing
rather than leaving forever — hence this note, since three inline comments in three repos will not
prompt anyone to check whether ruff has caught up.

Split out of the Python 3.15 pass, which is otherwise done (2026-08-18).

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

**A concrete candidate outside that set, 2026-08-16.** `raven/common/nlptools.py` declared `__all__`
as a **set** literal — almost certainly a slip, `{` and `[` being adjacent on a Nordic keyboard with
Emacs auto-closing the delimiter. It survived because Raven selects `E, W, F, SIM`, and the rule that
catches it, `PLE0605` ("Invalid format for `__all__`, must be `tuple` or `list`"), lives in `PL`.
Verified with `ruff check --select ALL` on a synthetic file. A set still works for `import *`, so the
failure is silent: it loses the house convention that `__all__` order mirrors the file, and nothing
complains.

`PLE` is the pylint *error* subset — small, and about things that are wrong rather than things that
are unfashionable, so it fits the house line on linters better than the broader `PL`. Worth pricing
across the fleet as part of this evaluation.

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

*Cluster: ci · Cost: M · Gate: the copy-vs-shared-checkout-vs-composite-action decision below · Filed: 2026-07-13 · See also: `pyan/tests/test_docs.py`*

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

**Part of this now exists in pyan, as a reference implementation** —
`tests/test_docs.py`, added 2026-08-20. It checks the README's hand-maintained table
of contents against the document's own headings (every heading listed, every entry
resolving, and in document order), and that anchor links in the prose resolve too. It
runs under `pytest`, so it needs no workflow change, and it is offline and
deterministic as this item requires. It found two headings that had been missing from
pyan's TOC since they were written, which is the failure mode exactly: adding a heading
prompts nobody to update the list, so the drift is silent until a reader clicks.

Two limits on reusing it as-is. It covers anchors only, not the relative-file-link and
docstring-path half wanted above. And its heading and TOC parsing assume pyan's README
format — Juha's note when it was written was that other projects would want this too,
but that it depends on each README's format, so it is a starting point rather than a
drop-in.

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

## Clean up the NVIDIA PyIndex pip config on the work machine

Done on the personal machine 2026-08-17; the work machine needs the same treatment, since this
is machine-local config that no repo carries.

`nvidia-pyindex` writes **two** identical files — `~/.config/pip/pip.conf` and
`~/.pip/pip.conf` — and both set three things worth removing:

- `extra-index-url = https://pypi.ngc.nvidia.com` and a matching `trusted-host`. The host no
  longer resolves, so every `pip install` pays two DNS retries before falling through to PyPI.
  CUDA builds of torch and friends are served from PyPI proper now.
- `no-cache-dir = true`, which disables pip's download cache globally and forces re-downloads.

What to leave: `index-url = https://pypi.org/simple`, the default anyway, which keeps the file
self-documenting rather than empty.

Two things found while doing it here, both worth checking there:

- **`nvidia-pyindex` is still installed** (1.0.9 here). It rewrites the config only at install
  time, so an idle copy is harmless — but reinstalling or upgrading it undoes this.
- **Some installed packages genuinely came from that index and are not on PyPI**: here,
  `nvidia-cublas-cu11 2022.4.8`, where PyPI carries `11.10.3.66` and `11.11.3.6` but no
  `2022.4.8`. Not an argument against the cleanup — the index is unreachable, so those versions
  are already unreinstallable — but it means such a reinstall fails either way, and the pip
  config will not be the reason.

Raised 2026-08-17, when the dead host's retries surfaced while building a Python 3.15 venv.

## PyPy: done, apart from a version that does not exist yet

**Resolved 2026-08-18.** Every fleet project that can run on PyPy now has a `pypy-3.11` job:
`mcpyrate` and `unpythonic` already did, and `chandra` was added (242 tests pass on PyPy
7.3.23, none skipped — the SD Prompt Reader interop test included, since pillow ships `pp311`
wheels). Nothing else is a candidate, and the reasons are settled rather than pending:

- **`pyan` cannot run on PyPy at all.** Not "the scope names differ" — **PyPy does not
  implement `_symtable`**, so the stdlib `symtable` module raises `ModuleNotFoundError` on
  import, and `import pyan` dies at `pyan/analyzer.py:9`. Verified directly on PyPy 7.3.23.
  pyan's entire scope analysis is built on `symtable.symtable()`, so there is no small fix:
  it would need its own scope resolution written against the AST. Do not re-open this on the
  strength of "PyPy is quite compatible these days" — check `_symtable` first, in one command.
- **`pylu`, `pydgq`, `python-wlsqm`** — Cython extensions through meson-python, wheels through
  cibuildwheel. PyPy would mean cpyext (slow by construction), `pp*` wheel identifiers, and a
  numpy build for PyPy. A project in itself, not a matrix row.
- **`raven`** — torch, spaCy, DearPyGui, chromadb, scikit-learn. Categorically out.
- **`arxiv-api-search`** — retired from the fleet (see `CLAUDE.md`). It was a candidate only
  because it used to be the setup reference, and chandra holds that role now.

`pypy-3.11` is the whole matrix, not a lagging entry: stable PyPy 7.3.23 implements Python
3.11 and nothing else (7.3.19 was the last to also ship 3.10; 3.12 exists solely as a
`nightly`, `stable=False`). **The one thing left is to add a row when PyPy ships a newer
language version** — at which point the aim stated originally applies again, that a project
supporting PyPy should support every language version PyPy supports.

Local PyPy for checking this by hand is in `NEW-MACHINE-SETUP.md`; there is no apt route,
deadsnakes being CPython-only and Ubuntu universe carrying a 2022 build.

Raised 2026-08-17; resolved 2026-08-18.
