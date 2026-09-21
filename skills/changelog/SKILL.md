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

**The target is the length needed to say what must be said, and not one word more.** Compactness is a *density* requirement, not a word count: cut back-story, never information. If dropping a word would hide what triggers a bug, or who is affected, or what the new thing actually is, the word stays.

That works out to different lengths per section, because the reader needs different things:

- **`Fixed`** is usually short. The reader already knows what the function is; they need to know what broke, under what conditions, and whether it could have bitten them. A sentence or two, with the trigger condition, is normally the whole job:

  > `unpythonic.misc.timer` / `unpythonic.timeutil.ETAEstimator`: switched from `time.monotonic()` to `time.perf_counter()`. Latent Windows-only bug: `monotonic` is backed by a ~16 ms tick counter on Windows, so microsecond-scale `with timer() as t: ...` blocks recorded `t.dt = 0.0` and downstream divisions raised `ZeroDivisionError`. POSIX unaffected.

- **`New`** runs longer, legitimately. A reader has to learn *what the thing is* before they can tell whether they want it — so a feature entry may well be a paragraph, with nested bullets for the caveats and consequences that come with it. That isn't verbosity; it's the minimum that does the job.

What goes in the commit message instead, in both cases: the diagnostic trail, the back-story, and why it was tricky.

## An entry is not documentation

This is what bounds the clause above, which otherwise has no upper end: "a feature entry may well be a paragraph" is true, and it will absorb an entire manual if nothing stops it. **The entry says what is new and what it is for. How to drive it goes in the README or the docs.**

The test is per sentence, and it is quick: *is this telling me something changed, or teaching me to use it?* A list of every key a new view binds, what each of its five box kinds means, which setting tunes its animation — all true, all useful, none of it a description of a change. It belongs where a user looks when they are using the feature, not where they look to find out what happened since the version they have.

The failure is not verbosity for its own sake. It is that the material ends up **only** in the changelog, which is the one document nobody re-reads: the README section that should have carried it never gets written, and the next release's entry has nowhere to point.

Measured on Raven, 2026-09-21, which is what prompted this: a single feature entry had reached 1395 words — longer than the longest entry in `unpythonic`'s entire history (1126) — and the in-progress release section was 20,748 words against 36,033 for the whole file across ten releases. The README already had a section on that feature.

### There is no word count, and the failure lives in the tail

**How long an entry should be depends on the feature** (Juha, 2026-09-21): the shortest prose that describes a thing clearly is a property of the thing, so a bound in words would be wrong for half the entries whatever number it took. That is why every rule here is about *what a sentence is doing* rather than how many there are.

What a measurement does say is **what normal looks like**, which is the thing a writer without years of these in their hands does not have. Across the fleet, 2026-09-21:

The eras split at **2026-02-05**, when the human-AI collaboration began; `unpythonic`'s changelog reaches back to 2018, so its left-hand rows are eight years of one person's judgement.

| corpus | entries | median words | longest | over 250 words |
|---|---|---|---|---|
| `unpythonic`, before the collaboration | 60 | 32 | 768 | 4 |
| `unpythonic`, since | 84 | 40 | 189 | 0 |
| `mcpyrate`, before | 76 | 28 | 321 | 1 |
| `mcpyrate`, since | 32 | 44 | 190 | 0 |
| Raven 0.2.8 | 94 | 73 | 394 | 6 |
| Raven 0.2.9 | 139 | 100 | 1334 | 14 |

**The fleet's typical entry is 30–45 words.** That is a distribution to recognize, not a limit to enforce — the 768-word entry in the left-hand column is a legitimate one, and the Kolmogorov point above is why. What it does mean is that an entry three times that length is unusual enough to be worth a second look, and a *section* whose median is three times it is describing something other than what changed.

**And length hides in a tail, so reviewing from the top finds nothing wrong for a long time.** In Raven 0.2.9, fourteen entries — a tenth of the section — held 35% of its words. Sort by length and read the longest five; that is where the documentation is.

**A related tell, when the writing itself is hard.** The Zen of Python says an implementation that is hard to explain is a bad idea, and one that is easy to explain may be a good one. Generalized beyond implementations — which is our extension and not the original claim — an entry that resists being written compactly is sometimes reporting on the *feature* rather than on the writing: a thing that takes 600 words to describe may be several things, or the wrong shape. Worth a moment's suspicion before concluding the entry simply needs to be long.

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

## The measure is whether the section is scannable

**The budget being spent is the reader's attention** (Juha, 2026-09-21). Every rule above is a way of spending less of it, and this is the one to apply where they do not reach: a reader arriving at a release section is looking for the two entries that affect them, and everything that makes the other forty easier to skip past is doing the job.

It also says where to **stop**. An item that is a single clause takes a title and nothing else, because splitting it yields a title and a sentence fragment — two lines spent to learn one thing, which is the failure this rule exists to prevent, arrived at from the other side.

### Line breaks

**One line per bullet**, unwrapped, however long it runs. This is what the fleet's changelogs already do — measured 2026-09-21, `unpythonic` 267 long lines against 93 wrapped, `mcpyrate` 106 against 42 — and the reason to keep to it is that a file wrapped in places and not in others makes the mixture visible where neither style alone would be. A bullet that runs long wants **nesting, not wrapping**: see the section above.

### When a section grows past scanning

A release section long enough that a reader scrolls looking for the entry that concerns them wants its entries **titled**: the bold lead on a line of its own, the prose starting on the next line, indented to the item's content column and with no blank line between them. Markdown folds the two back into one paragraph, so this is a shape the source has and the rendered page does not — which is the point, since the source is where the entries are written and rearranged.

Reach for it when the section is long enough to need it. Raven's 0.2.9 is the case that produced the rule: 139 top-level entries across three sections, at which size a lead that runs into its own prose gives a reader nothing to skim.

**This style is fleet-wide.** What *does* vary per project is release mechanics (tag format, the dev-version suffix), and that lives in the `release` skill, along with the post-release stub. Raven additionally groups entries under component headers, since it ships many apps from one repository; that one is in its own `CLAUDE.md`.
