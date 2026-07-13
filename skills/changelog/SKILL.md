---
name: changelog
description: House style for writing CHANGELOG.md entries — changelogs are for users (not a commit log), they cover only changes since the last tagged release, and entries are compact (one sentence, two at most). Use whenever adding or editing an entry in a CHANGELOG.md, writing up a bugfix for users, deciding whether a fix even belongs in the changelog, or reviewing changelog wording. Applies while fixing the bug, not only at release time.
---

# Writing changelog entries

Write the entry **when you make the change**, not at release time. Reconstructing months later from `git log` loses exactly the trigger conditions that make an entry worth reading.

## Changelogs are for users

Describe what changed from the user's perspective: which tool, and what it does differently now. Internal details — refactors, function renames, test additions — don't belong in the main sections. If they're worth recording at all, an "Internal" subsection per version is the place.

## Only changes since the last tagged release

A bug introduced *and* fixed inside an unreleased development window never reached a user. It is invisible to the audience the changelog is written for, so it doesn't go in the changelog. Its archaeology belongs in the commit message and the PR description.

The test when adding a `Fixed` entry: **was the broken behavior present in the most recent tagged release?** If no, drop the entry — the fix is internal cleanup.

## Compact entries

Changelog lines are not commit messages. One sentence, two at most: what changed, on what platform, and — for a latent bug — the trigger condition. The back-story, the diagnostic trail, and the "why it was tricky" go in the commit message body.

Compactness means removing back-story, not removing information. If cutting a word would hide *what triggers the bug* or *who is affected*, the word stays.

Target density:

> `unpythonic.misc.timer` / `unpythonic.timeutil.ETAEstimator`: switched from `time.monotonic()` to `time.perf_counter()`. Latent Windows-only bug: `monotonic` is backed by a ~16 ms tick counter on Windows, so microsecond-scale `with timer() as t: ...` blocks recorded `t.dt = 0.0` and downstream divisions raised `ZeroDivisionError`. POSIX unaffected.

Reference for the style: `unpythonic` v0.15.3 and earlier.

## Nest subordinate detail; don't flatten it

When an entry has detail that *belongs to it* — a caveat, a consequence worth knowing, an error taxonomy — put it in nested bullets under the entry rather than cramming it into the lead sentence or splitting it into a sibling entry. The lead bullet says what changed from the user's point of view; the children carry what a user of *that* change then needs to know.

```markdown
- `unpythonic.dialects.befunge`: a Befunge-93 interpreter wrapped as a whole-module
  source dialect. [...]
  - Demonstrates the `mcpyrate` `Dialect.transform_source` hook for a different shape
    of source language than `bf` [...]
  - Three error categories: `SyntaxError` for source-level malformation, `IndexError`
    for runtime out-of-grid `g`/`p`, and `UnknownOpcodeError` [...]
  - The module docstring above the dialect-import is the recommended way to comment a
    Befunge file (`#` is a real Befunge command, so comments inside the body aren't
    supported).
```

Flattening these into siblings would imply they're independent changes; folding them into the parent sentence would bury them. The nesting *is* the information — see the "flat is better than nested, except when nesting carries meaning" rule in `CLAUDE.md`, which applies to prose as much as to code.

**This style is fleet-wide.** What *does* vary per project is release mechanics (tag format, the dev-version suffix), and that lives in the `release` skill, along with the post-release stub.
