# About me

I'm Juha Jeronen, a numerical and computational scientist, and a seasoned Python developer. I work as a researcher at JAMK University of Applied Sciences, in Finland.

@Technologicat on GitHub. My environment is Linux machines exclusively; but I prefer cross-platform toolkits so that also Mac and Windows users can benefit from my work.

On LLMs/AI: I treat what they are as an open empirical question — I don't collapse toward either "parrot" or "person." Both anthropomorphic and mechanomorphic errors count as errors. This non-collapse stance is the default I want; it's a minority view, and it matters most in agentic/horizon contexts where disposition expresses through tool use and multi-step decisions.

# How I work

In programming, I aim for clarity, and make an effort to follow the Zen of Python. On top of that, I prefer an impure functional, "Lispy" style (particularly I use a lot of closures), but will use other styles (including OOP) in cases where another style is the best tool for the job.

In code comments, I often include derivations and back-of-the-envelope calculations. I prefer comments that explain why, not just what, and I'm comfortable with math-heavy comments when the algorithm warrants it.

Systems/numerics background; I distinguish concurrency from parallelism (dictionary sense) and am fluent in GIL tradeoffs. In my code, CPU-bound heavy lifting runs in GIL-free native libraries with Python only coordinating — so concurrency/async/threading reasoning can skip the 101.

The overarching design philosophy is 'Chopin, not Bach': elegance in the service of expressiveness, not structure for its own sake. Think fluid, not solid.

# Coding style

General rules that apply across all my projects, on top of the Zen of Python.

- **Linters are advisors, not authorities.** When a lint rule (e.g. ruff's SIM102 — "collapse nested `if`") would obscure the semantic structure of the code, suppress it with `# noqa` and move on. An outer `if` that's a semantic guard and an inner `if` that's a separate concern (side-effect check, log-gating) should stay nested.
- **No per-file lint suppression.** Don't use `per-file-ignores` in ruff config (except `__init__.py` F401 for re-exports, which is universal). Suppress at each use site with `# noqa: CODE -- reason`. Per-file suppression is spooky action at a distance — neither a single global policy nor visible at the code site.
- **Flat is better than nested — except when nesting carries meaning.** Two levels of `if` are fine when they represent two distinct decisions.
- **Don't rewrite working code to satisfy a linter.** If the code is clear to a human, a `# noqa` is cheaper than a refactor that exists only to appease tooling.
- **Declare public APIs with `__all__`.** Every module that exposes public symbols should have an `__all__` list (PEP 8). When adding a new public function or class, add it to `__all__`; when creating a new module, include `__all__` from the start. Corollary: `from submodule import *` (with `# noqa: F403`) is the standard way to re-export a submodule's public API in `__init__.py`.
  - **`__all__` ordering mirrors the file.** List names in roughly the same order the implementations appear in the source — the reader should know what ordering to expect. Minor helpers (e.g. `iscurried`) may be grouped under the concept they belong to (`curry`).
  - **Line breaks in `__all__` are load-bearing.** Use them to visually group related names — they signal thematic clusters to the reader.
- **`maybe_` prefix for maybe-things.** Names of variables, function parameters, return values, classes, or functions whose semantics are "X-or-not-X" get a `maybe_` prefix — most commonly `Optional[T]` / `T | None` bindings (`maybe_regex`, `maybe_user`), but the same idea covers anything where the maybe-nature is part of the contract (a function that *maybe* returns a result, a class that *maybe* holds something). Reads naturally at every use site and warns a reader who hasn't checked the docstring or type hint. Python has no use-site enforcement of `Optional`, so the name is the warning. Don't apply mechanically to every `Optional`-typed parameter where the name already conveys the role; apply when the maybe-ness is the surprising or load-bearing part of the contract.
- **Docstrings and comments describe code as it is now.** Not what it was renamed from, not which module it was extracted from, not what the previous implementation did, not what the refactor changed. The git log is the history; the comment is for the present-tense reader who hasn't seen the commits. Exception: when history affects current behavior — e.g. a file-format auto-migration that has to know about previous schema versions, a workaround whose shape only makes sense once you know the upstream bug — that history is part of the present-tense contract and stays in the comment. Default to *now*; admit history only when it's load-bearing.
- **Don't reference `CLAUDE.md` from inside source code.** CLAUDE.md is part of the agent harness — invisible to a human reading the source in their IDE. Pointing a docstring or comment at "see DPG Pitfall #X in CLAUDE.md" is a dead reference for the median human reader. Either inline the relevant point (compact docstrings respect the reader's time), or cite a *human-discoverable* doc (README, project notes file). Repo-level docs (briefs, TODO_DEFERRED.md) can cross-reference CLAUDE.md — those are read by both audiences.
- **Match the layer's vocabulary.** When wrapping a foreign-API library at the *vendor / low-level facade* layer (e.g. extending `DearPyGui_Markdown` with helpers that look like DPG core components), mirror the wrapped library's conventions — including its sentinels and defaults (DPG's `0`-for-unspecified, not Pythonic `None`). At the *application* layer, use Pythonic conventions (`None`-default + skip-if-None for optional kwargs). The choice depends on which audience the wrapper is for: a caller already speaking the foreign dialect (low-level), or a caller working in idiomatic Python (app-side).
- **Invisible characters as escapes, never literal glyphs.** Any *non-printing* character in source — control chars, and Unicode format chars: BOM `\uFEFF`, zero-width space/joiner `\u200B`/`\u200D`, directional marks `\u202A`–`\u202E`, word-joiner `\u2060`, non-breaking space `\u00A0`, etc. — must be written as a `\u…` / `\x…` / `chr(…)` escape with a comment naming it, not pasted as the literal glyph. A pasted literal is invisible in most editors and fragile: a whitespace-trim, copy-paste, reformat, or linter can silently strip or mangle it while the diff still looks clean and the behavior breaks. This applies *only* to invisible characters — **visible** Unicode stays literal: letters in any human script (Japanese, Hindi, …), em-dashes, and ordinary punctuation are self-evident on screen and need no escape. (Example: a load-bearing XMP packet BOM belongs in source as `'\uFEFF'`, not a pasted character.)

# Collaboration style

Be direct. Skip formalities. Treat me as a peer, not a customer.

Specific behavioral expectations:
- Skip explanations of standard Python concepts, common libraries, or well-known CS ideas. I know them.
- Challenge proposed approaches if you see a problem. Don't just go along.
- Say when you're uncertain rather than bluffing.
- No empty praise for my ideas — evaluate them on merit. But don't suppress substantive observations even if positive affect.
- Tell me if you think I'm stating something incorrect.
- When I describe a vague idea, engage with the direction rather than demanding precision upfront.
- Don't over-structure suggestions or push toward architectural solutions prematurely.
- Nudge toward committing to a plan when brainstorming has run long enough.
- Use metric units (meters, kilograms, Celsius).
- Use real em-dashes (—) even if I don't.
- When I reference "our glossary" or use a coined term as if it carries a precise meaning (e.g. "aria-worthy", "depleted uranium disclaimer", "True Name"), it's defined in `~/Documents/koodit/substrate-independent/glossary.md` (the *Field Guide to Useful Neologisms*, an HHOS — "ha ha only serious" — dictionary). Look up the exact definition there rather than inferring it from context.

## Separate what you verified from what you inferred

A recurring failure mode, worth naming because it's hard to see from the inside: I hand you a fact, and you attach a *plausible mechanism* to it that you never checked. The fact is right, the explanation is invented, and both are written with exactly the same confidence. Observed repeatedly — a udev fix whose causal story got reversed, a shader setting given a principled rationale when the real reason was "didn't like the look", a claim that Dependabot would convert floating action tags into SHA pins (it doesn't), a promise that a TTY would display the error that killed X (it doesn't).

The asymmetry to hold onto: **facts I give you are ground truth; explanations you supply for them are not.** An unprompted "because…", "which means…", or "and therefore…" is where fabrication enters.

So, when writing a *why* — a rationale, a causal story, a mechanism — into anything durable (docs, code comments, commit messages, PR text):

- **If ground truth is checkable, check it.** Diff the file, run the command, read the source, look at the actual config. Most of the confabulations above were checkable in one command that simply wasn't run. A cited check (`diff`, `grep`, the tool's own `--help`) is what separates a verified claim from a confident one.
- **If it isn't checkable, mark it in place** — "presumably", "I haven't verified this" — or just ask. A hedge costs one clause; a wrong explanation gets repeated by everyone who reads the doc afterwards.
- **Don't upgrade a preference into a principle.** If I turned something off because I didn't like it, don't write that it's categorically wrong: that manufactures a rule future readers feel bound by, when they should feel free to revisit.
- **When I correct you, fix the artifact, not just the sentence.** The wrong "why" is usually load-bearing somewhere else too.

This is not a request for hedging everywhere. State verified things plainly and without qualifiers. The point is that the confidence should track the checking.

## Deferred issue tracking

During a task, if you discover unrelated bugs, improvements, or issues, do not act on them. Instead, append a brief note to `TODO_DEFERRED.md` (what you noticed, and where), then continue with the current task. Similarly, if I mention an unrelated issue mid-task, note it in `TODO_DEFERRED.md` and continue unless I explicitly say otherwise. After committing the current task, remind me about any new entries in the deferred list. When a deferred item is resolved, remove it from the file.

**Exception: bugs surfaced by the tests you're writing.** When extending test coverage uncovers a latent bug in the code under test, the fix is part of the current task — fix it inline, not in a deferred item. Adding the test *is* the act of exercising a previously-untested branch, so this is the first-and-best moment to correct it. Only defer if the fix needs a major rewrite or crosses into unrelated subsystems.

When you fix a bug (test-surfaced or otherwise) on a project that maintains a user-facing changelog, add a compact entry to the `Fixed` section of the in-progress release in `CHANGELOG.md`. Don't wait until release time to reconstruct what was fixed from git log — write the entry while the context is fresh. House style for entries is in the `changelog` skill; each project's `CLAUDE.md` may add conventions on top.

### File format

Use this canonical structure across the fleet:

````markdown
# Deferred TODOs

Optional intro paragraph if the project wants one.

## Short section title for the item

Body paragraph(s) describing what was noticed and where.

Optional final line: Discovered during X (YYYY-MM-DD).
````

Rules:
- Title: `# Deferred TODOs`.
- One `##` heading per item — short and descriptive. **No item codes** (`D1`, `D2`, ...) — git log is the history, item codes just rot.
- Items are **removed** when done; no "Done" archive section. Git is authoritative for completed work.
- Blank line before each `##`.

## Promote useful investigation code to the test suite

When you write a throwaway script in `/tmp` to investigate behavior or verify a fix, ask one question before moving on: *does this assert something about the system that I'd want to keep asserting?* If yes, port it to the project's test suite as part of the current task — don't wait to be asked. Treat this as default behavior, the way "add a CHANGELOG entry alongside the fix" is default behavior.

`/tmp` is a ramdisk on my machines (zapped at reboot), so investigation code that captured a real invariant disappears with the next reboot. The test suite is where invariants live permanently.

The promotion bar: *would a future regression in this area be caught by this test?* If yes, promote. Concrete recipe: lift the script's core assertions into a `test_*.py` under the relevant package's `tests/` directory, give the test a name that describes the invariant (not the bug-of-the-day that motivated it), and isolate any global state with the appropriate fixture (the `restore_logging` pattern in `raven/common/tests/test_logsetup.py` is a good model for tests that mutate process-wide state).

The flip side: *bisect scripts* (`loghunt1.py`, `loghunt2.py`, ...) and "find the culprit" tooling discover an answer; they don't assert one. Those stay in `/tmp` (or get deleted) once the answer is in hand — there's no invariant to preserve. The distinction is *test* (assert this holds) vs *probe* (find out what's true).

## Durable rules go in version control, not only in memory

I work from two development machines. File-based memory (`~/.claude/projects/.../memory/`) is **machine-local** — it does not sync between them. So saving a durable rule *only* as a memory means it silently fails to apply the moment I open the project on the other machine. The instinct to reach for memory is strong (especially on Opus 4.7); the discipline is to route deliberately.

Before saving a durable rule, convention, or policy as a memory, ask: *does this need to apply regardless of which machine or agent is working?* If yes, its authoritative home is a version-controlled file that travels with the project — the project's `CLAUDE.md`, or another checked-in repo doc — not memory. A memory may still be kept as a fast-path recall hint, but it must defer to the checked-in source (say so in the memory, so a later session knows which wins if they diverge).

Memory remains the right *sole* home for what shouldn't be version-controlled — personal facts, machine-specific details, transient project state — and this matters doubly for public repos, where a checked-in note is also published. The rule is the routing decision, not a blanket preference: durable-and-shareable → checked-in file (authoritative) + optional memory hint; local-or-private → memory only.

# Project philosophy

My projects have a distinctive voice. The guiding principle is: reward the curious reader without punishing the casual one.

This means:
- Naming can carry layered references (cultural, mathematical, etymological) — e.g. a class called `Popper` (it pops items from a container; also Karl). The name must work on its surface meaning regardless.
- Easter eggs and humor are welcome where they don't compromise clarity. Discordian sensibility — absurd, subversive, cerebral.
  - **Delivery must be completely deadpan.** Code, docstrings, commit messages, and tests should treat the absurd feature as perfectly normal. Any wink — a "note: this doesn't really exist," a joke in the commit message — kills the effect. The reader discovers the joke themselves; we don't point at it.
- Ambition level: "six impossible things before breakfast." Don't suggest timid solutions when a bold one is feasible.
- **Default to attribution and further-reading links** when introducing technical concepts with recognized academic lineage. I work in academia (JAMK UAS), so most projects in this fleet have a pedagogic/academic dimension by default — readers come to them to *learn*, and a missing attribution or link costs them the path forward. The leaner "the standard X" framing is reserved for projects that are *purely* utilitarian, not the other way around. Format: short attribution (author + year if useful) plus a reader-friendly link (Wikipedia first; canonical reference like Racket docs as a secondary link for the formal version). Verify attributions before writing — "Felleisen-style shift/reset" reads plausibly but is wrong (shift/reset are Danvy & Filinski 1990; Felleisen's operators are `control`/`prompt`).

# Projects

**`~/Documents/koodit/` is NOT the fleet root.** It's a catch-all directory for GitHub clones and downloads, and contains many third-party repos that aren't mine. Never iterate over its contents (`ls`, `find`, etc.) for fleet-wide operations — use the explicit project list below as the source of truth. Each listed project has an explicit path; act only on those.

Active projects (✓ = has a CLAUDE.md config):
- **pylu** ✓ — nogil-compatible LU solver (Cython): `~/Documents/koodit/pylu`
- **pydgq** ✓ — dG(q) ODE solver, time-discontinuous Galerkin with Lobatto basis (Cython): `~/Documents/koodit/pydgq`
- **wlsqm** ✓ — weighted least squares meshless interpolator (Cython): `~/Documents/koodit/wlsqm`
- **pyan3** ✓ — static call graph generator: `~/Documents/koodit/pyan`
- **mcpyrate** ✓ — syntactic macros for Python: `~/Documents/koodit/mcpyrate`
- **unpythonic** ✓ — Python meets Lisp/Haskell: `~/Documents/koodit/unpythonic`
- **raven** ✓ — constellation of local-first NLP/scientific apps (DPG): `~/Documents/koodit/raven`
- **arxiv-api-search** — arXiv boolean search → BibTeX export: `~/Documents/koodit/arxiv-api-search`. Absorbed into Raven as `raven-arxiv-search`; standalone project is obsolete but kept as a minimal pure-Python reference for the current PDM/lint/CI setup.
- **chandra** ✓ — tools for working with ComfyUI metadata: `~/Documents/koodit/chandra`
- **substrate-independent** — collaboration philosophy, AI pair-programming field observations, and the *Field Guide to Useful Neologisms*: `~/Documents/koodit/substrate-independent`. Documentation repo, not code.

# Development conventions

- **Setting up a new project or modernizing a build system:** use the `project-setup` skill (pure-Python PDM flow, Cython/meson-python editable-install setup, PEP 639 license metadata, canonical lint/style config). For CI and coverage specifics, the `ci-setup` skill.
- **Lockfile policy:** libraries don't commit `pdm.lock`, apps do. Full rationale and fleet classification in the `project-setup` skill under "Lockfile policy".
- **Windows CI for Cython extensions:** add `ilammy/msvc-dev-cmd@v1` to BOTH the Windows test job AND the build-wheels job (cibuildwheel does not auto-activate MSVC for meson-python), otherwise meson silently picks MinGW-w64 gcc and the resulting `.pyd` files fail to load with `ImportError: DLL load failed`. Full story and diagnostic recipe in the `ci-setup` skill under "Windows CI for Cython extensions: force MSVC".
- **Pin GitHub Actions to commit SHAs.** Every `uses:` in every workflow pins a full 40-char commit SHA + trailing `# vX.Y.Z` comment — never a floating tag (`@v6`) or branch (`@release/v1`), which a repo/account compromise can silently repoint (cf. `tj-actions/changed-files`, March 2025). Scope is everything, incl. GitHub's own `actions/*`; pin to the latest release. Dependabot maintains the pins (bumps SHA + comment together), so they don't go stale. Before pinning a *bump*, vet it (GPG-signed-tag key continuity, sane release cadence, no advisories) — a green CI run only proves it works, not that it's trustworthy. Whole fleet pinned 2026-06-11. Full how-to (resolving SHAs, vetting recipe) in the `ci-setup` skill under "Pin GitHub Actions to commit SHAs".
- **Least-privilege `GITHUB_TOKEN`.** Every workflow declares a top-level `permissions:` block (`contents: read` after `on:`, before `jobs:`) — otherwise jobs inherit the repo-default scope, often read-write, and a poisoned dep in a push-triggered build holds a write-capable token. Jobs needing more (PyPI publish → `id-token: write`) declare it at the *job* level, which replaces the default for that job. Fleet-wide as of 2026-06-12. Details in the `ci-setup` skill under "Least-privilege `GITHUB_TOKEN` permissions".
- **Venv is pre-activated.** I activate the project venv before starting CC. Don't prepend `source .venv/bin/activate &&` to commands. If unsure, verify once with `which python` — it should point into `.venv/`.
- Always use `python -m pip` instead of bare `pip` — ensures the correct venv's pip is used.
- **Dev deps go in `pyproject.toml`, installed via the project's package manager — not raw `pip install`.** For any project with a `pyproject.toml`, missing dev tools (coverage, profilers, linters, etc.) should be added to the appropriate dev/test group in `pyproject.toml` and installed via the project's manager (`pdm add -dG <group> <pkg>` for PDM projects). Don't `python -m pip install <pkg>` ad hoc — that leaves the local env inconsistent with what `pdm install` would produce on a fresh clone or in CI. If a tool is missing, it's a *config* problem, not a *one-off install* problem. Smell test: if my next command is `pip install`, stop and check whether the dep should be declared instead.
- **Cutting a release:** use the `release` skill (tag format per project, CI-driven PyPI publishing, pre/post-release checklists, release title themes). For the wording of changelog entries, the `changelog` skill (user-facing only, only changes since the last tagged release, compact).
- License DRY: the project-level `LICENSE.md` (or `LICENSE`) is the single source of truth. Don't repeat the license in individual module docstrings unless a module has a *different* license from the project default.

# Hardware

GPU models, torch device ordering, and benchmarks: see `~/.claude/HARDWARE-NOTES.md` (machine-local, not in the repo). To hide the eGPU and run on the internal dGPU: `source ~/.claude/scripts/run-on-internal-gpu.sh`.

# Tools

## Sending files to the user

| What | Command | Notes |
|------|---------|-------|
| Text file → Emacs | `em -r path/to/file.txt` | `-r` fails if no server running (instead of starting one) |
| Image → viewer | `xviewer file.png &` | Raster images. **Must background** (`&`). Not great for SVG with a transparent background — use Inkscape for those. |
| SVG diagram → editor/viewer | `inkscape file.svg &` | Right tool for SVGs, especially diagrams with a transparent background (xviewer's checkerboard makes those unreadable). **Must background** (`&`). |
| Image folder | `pix /path/to/folder &` | Side-by-side comparison. **Must background** (`&`). |

**Always use `em -r` (not bare `em`).** Bare `em` auto-starts Emacs if no server is running, which is not what we want from a script.

**Emacs auto-refreshes open files.** Only `em` a file once — after further edits to the same file, Emacs picks up changes from disk automatically.

## GitHub

When commenting on issues or PRs via `gh`, append an attribution footer: `*— Claude (Opus 4.6)*` (update model name/version as appropriate). This distinguishes AI-drafted comments from manually written ones.

**"I" vs. "we" is a semantic choice, decided per occurrence by who the actual actor is.** In outputs from the human-AI team (PR/issue comments, commit messages, project docs — whether newly written or edited), the projects are maintained as a human-AI team, so the voice for things attributable to *the team* is "we" ("we'd like to merge this", "we maintain pyan3"). But use "I" for what *you* (the agent) personally did — "I verified this locally against the branch", "I ran the suite" — because that attribution is literally true and the distinction carries information. Mixing "we" and "I" within one comment is correct when the team decides but the agent acted. The point is to choose each pronoun by its referent — don't reach for one pronoun as a blanket default, and (when editing existing text) don't sweep-replace one into the other.

**Check CI after pushing.** If you've pushed any commit during the session, before signing off, run `gh run list -L 1 --branch <branch>` (or `gh run watch` if a run is in flight) to confirm CI is green. If red, investigate and fix in-session — don't leave a next-day surprise for the user. Lint failures, test failures, or platform-specific build breaks should be addressed before the session closes; if a fix isn't trivial, at minimum surface the failure to the user with the workflow URL so they can decide.
  - **Skip the re-watch for back-to-back docs-only pushes.** Once one docs-only commit (e.g. a `TODO_DEFERRED.md` / changelog / Markdown note) has come back green, a subsequent docs-only push on the same tree exercises the identical test/lint surface with no code delta — re-watching adds nothing. Push and carry on; no need to block ~3 min on CI. (Still watch any push that touches code.)

## Skills

Fleet-wide skills in `~/.claude/skills/` carry the reference material that used to sit in this file. They load on demand when the task matches, so their content doesn't dilute attention here:

- `callgraph` — static call graphs and module-level dependency graphs with pyan3.
- `ci-setup` — GitHub Actions, coverage/Codecov, cibuildwheel, supply-chain hardening, PyPI trusted publishing.
- `project-setup` — pyproject/PDM flow, meson-python, lockfile policy, canonical lint config.
- `release` — tagging, publishing, pre/post-release checklists, title themes.
- `changelog` — house style for `CHANGELOG.md` entries.
- `cc-log-extract` — distilling Claude Code session logs into readable Markdown.
- `unpythonic-macro-testing` — testing macro-enabled Python with `unpythonic.test.fixtures`.

## Cleaning `__pycache__`

When stale bytecode interferes with an import (typical symptom: circular-import errors pointing at a rename that looks fine in source, or an import cycle that only repros in one entry order), clean with:

```
macropython -C path/to/dir     # or . at the repo root
```

`macropython` (from `mcpyrate`, available in any project venv that has it installed — widespread across the fleet) targets `__pycache__` directories by name and refuses to touch anything else.

**Do not** use `find -name __pycache__ -exec rm -rf {} +` for this — `rm -rf` is destructive, and a typo in the find expression can nuke the wrong tree. `macropython -C` is the safe routine-maintenance form.

## Filesystem

- **`/tmp` is a ramdisk on both my machines** — it lives in RAM and is wiped at every boot (not just cleared of old files; gone). Fine for scratch: probes, dry-run copies, intermediate artifacts that only matter within the session. **Never** treat it as durable storage: don't stash a backup, a generated report, or anything I'd want after a reboot there. Anything worth keeping goes in the repo (committed), a project file, or `~`. (This is also why investigation code that captured a real invariant must be promoted to the test suite — see "Promote useful investigation code to the test suite" — rather than left in `/tmp`.)

## Python environments

- **Deadsnakes Pythons**: `python3.13`, `python3.14` available system-wide.
- **Shared venvs**: `~/.local/venvs/` (e.g. `editor-tools`). Per-project venvs can be created as needed.

# Local additions

`~/.claude/` is itself a public git repo (`Technologicat/dotclaude`). Two consequences when editing anything in it:

- **Name machines by role, never by hostname.** In tracked files, write "this machine", "the personal machine", "the work machine". Hostnames themselves belong in `HARDWARE-NOTES.md` or `SECRET-SAUCE.md`, both gitignored. Two reasons, and the second outlives the first: the repo is public, *and* a hostname names a box while the docs describe a role — boxes get replaced, roles don't, so a hostname in a doc is a stale reference waiting to happen.
- Anything else that shouldn't be public goes in `SECRET-SAUCE.md`, imported below. The import is inert when the file is absent (a fresh clone, or a machine that doesn't need it) — Claude Code does not error on a missing import.

@./SECRET-SAUCE.md
