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
| Raven, before (0.2.1–0.2.4) | 17 | 108 | 589 | 3 |
| Raven, since, through 0.2.8 | 139 | 72 | 394 | — |
| Raven 0.2.9 | 139 | 100 | 1334 | 14 |

**A library's typical entry is 30–45 words, and an application's is two to three times that.** Both halves matter. The first is a distribution to recognize rather than a limit to enforce — the 768-word entry in `unpythonic`'s left-hand row is a legitimate one, and the Kolmogorov point above is why. The second is why the number cannot simply be carried across: Raven ran a median of 108 words before the collaboration and 72 during it, so its distance from `unpythonic` is a property of *describing an application*, where a user-facing change has a screen and a gesture in it and a library's has a signature. Compare a section against its own project's history, not against the fleet's smallest number.

**What does transfer is the tail.** In every row above, the long entries are few and hold a large share: three of Raven's seventeen solo entries are 52% of that era's words, four of `unpythonic`'s sixty are 41% of its. That is the normal shape when the long ones are genuinely load-bearing. It becomes the failure above when they are documentation instead, which is what Raven 0.2.9's fourteen are.

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

**This rule says where detail goes, never whether it should be there**, and that is half a job. It is read at the moment something has just been written and a place is wanted for it, so an urge to include arrives and finds an approved shape waiting. Nesting is for detail that has already survived the section below; a child bullet is not a way of keeping something that did not.

## Omit the gloss

**An entry reports; it does not persuade.** That is what makes the gloss droppable: a clause arguing that the new behaviour is the right one answers a question the reader never asked, since they are deciding whether this release affects them rather than whether it was well designed.

**So almost always, the clause explaining the sentence can go.** It is the single most reliable cut, and the punctuation is the tell: a comma, dash or semicolon followed by *so*, *because*, *which means*, *instead of*, *rather than*, *where*. Cut there and what remains is nearly always complete.

**A gloss survives when it states a consequence the reader will meet** — a limitation, a guarantee, or what work the feature saves them:

> …the graph covers the subtitles, **so subtitling is not available while the graph is up**
> …a round of three or more tool results folds into one box, **so a turn that consulted five web pages does not fill the picture with plumbing**
> …a **…N more** box counts the matches behind it, **so a search result never hides behind one**

**It goes when it justifies the design, narrates the old behaviour, or repeats the point:**

> …it draws a dashed box, ~~because a branch that simply stopped being drawn would read as a branch that ends~~
> …an attached document shows its file type's icon, ~~so a message that is nothing but attachments no longer reads as an empty one~~
> …clicking previews and a second click commits. ~~So the whole tree can be explored without committing to anything.~~

**A title is a name, not a description, and it takes the same cut.** The clause after the comma goes there too: *"a Thinking toggle, for asking a reasoning model to just answer"* becomes *"a Thinking toggle"*, and what the qualifier said moves into the body or turns out not to have been needed. *"What the thinking cost is now reported, where before the single largest consumer of a reasoning turn had no numbers on it"* becomes *"the thinking cost is reported"*.

**Evidence goes, and the claim it supported stays.** An entry states what is true; it does not exhibit why you should believe it. A demonstration — *"asked for `1234 * 5678` with reasoning off, Qwen 3.6 reached for the calculator rather than answering from its head"* — is replaced by the sentence it was evidence for, and a measurement quoted in support (*"1.6 s on a 10k-token chat"*) simply goes. This is the persuasion rule again from its other side: not only *don't argue the design is right*, but *don't prove the claim*.

- **Cutting the evidence can cut a hedge that was riding on it**, and that is the one way this rule makes an entry *worse*. Losing "observed on that model rather than promised for all of them" left an entry asserting something broader than anybody knew. Before cutting, ask which claims the evidence was *limiting*, not just which it was supporting — and keep those limits in a clause.
- **A caveat survives on the counterfactual, with the reader as the actor**: would somebody deciding whether to use the feature plausibly assume the wrong thing without it? If yes it steers a real tendency; if no it is a *depleted uranium disclaimer* and goes with the rest. The reader, not the maintainer — what is obvious to somebody who knows how it works is exactly what the entry cannot rely on.

**Cut a specific the code can change without telling you.** A different test from the one above, and it fires on true, useful, non-evidential detail: *"what the GUI receives as fifteen events"* is accurate, concrete, and wrong the next time somebody adds a callback — and nothing will ever recheck it. In the fleet's glossary this is a **Chekhov's landmine**: a claim true when written that decays silently and detonates under a reader who has no reason to doubt it. The tell is a count, a version, a model name, or a *"there is no way to…"*.

- The repair is usually deletion rather than maintenance: *"as events"* says what the sentence needed and cannot rot.
- **A dated record is not one.** A measurement, a testing history, a stored sample naming what produced it — those are pinned to their moment on purpose, and the pinning is what makes them true.

**When a gloss is cut, do not let an intensifier fill the gap.** *"Analyzed afterwards without hand-rolling a tree walk"* became *"easily analyzed afterwards"*, which drops the one concrete thing the clause was for and keeps only the claim that it is nice. If what is left is *easily*, *simply*, *powerful* or *seamlessly*, the cut took the wrong half.

**Name a thing by the path a reader could use.** `agent.turn` becomes `raven.librarian.agent.turn`. An entry naming an API is read by somebody who wants to go and find it.

**"No longer" and "used to" are tells — in an `Added` entry.** There a before-and-after reads as information while being a fact about the *previous* release, which the reader is leaving: nobody was relying on the absence of a feature, so the old picture is decoration and the entry already implies the change by existing.

**In `Changed` and `Fixed` they are the point, and the before-picture is load-bearing.** Somebody *was* relying on the old behaviour — that is what makes it a change rather than an addition — so the old picture is the only thing that tells a reader whether this happened to them. *"Previously the stored system prompt was overwritten at every app start, so a conversation you had last month silently acquired today's instructions"* is not back-story; it is the audience test, and in the edit that produced this rule it was promoted from inline prose to a bullet of its own rather than cut.

So the rule is not *cut the before-picture*. It is **cut it when nobody was relying on it**, which is always in `Added` and never in the other two.

The reasoning that comes out is usually true, usually good, and already written down where it belongs — in the commit message that made the change, and in the comment beside the code. It is being cut for its audience, not for its accuracy.

**If careful editing does not shorten an entry, the length is not in the writing.** That is a test, and it costs one attempt. Edit it down until every remaining word is structural — *Little Prince mode* — and read what the attempt returns. An entry carrying gloss gives up a sixth of itself. An entry carrying documentation gives up nothing, because editing cannot move content and misplaced content is the only thing wrong with it.

Both halves measured on Raven the same afternoon. The chat graph entry went 1334 words to 1127 under an edit that *added* seven sub-bullets. The `raven-deduplicate` entry, restructured just as thoroughly — fifteen bullets to thirty-one — went 1070 to **1073**, three words longer. Its author's reading: "very little-princey already, no non-load-bearing words to remove". A user manual does not get shorter by being written better.

Derived from a real trim rather than from introspection: Raven's chat graph entry, 2026-09-21, where nine of the maintainer's cuts began at exactly this punctuation and every gloss he kept was a consequence rather than a justification. Worth knowing too that the trim removed **16%** while the sub-bullet count went *up*, 26 to 33 — most of the work was splitting walls of text into nested points, and the gloss removal rode along on top.

## A `Fixed` entry answers "did this bite me?"

That question is different from the one `Added` and `Changed` answer, and three things follow from it.

**One entry per fault.** If a reader may have hit one and not the other, one entry cannot answer for both. **The word "Separately," is the tell** that an entry is two — in the edit this came from, a caching bug and a background-thread race shared a heading, and splitting them cost nothing: 814 words to 813, six top-level entries to seven.

**Lead with the symptom; subordinate the mechanism.** The reader's question is *is this the thing that happened to me*, and only the symptom answers it. In that same edit the symptom rose to the top — the cycle advances, the overlay number changes, the image never appears — and the cause dropped a level beneath it, a third level of nesting appearing to hold it.

- **This is a judgement call, not an automatic cut, and it was a close one** (Juha, 2026-09-21). A detailed bug description usually does not belong in a changelog; the diagnostic trail belongs in the commit message. What earns its place here is **detail about the symptom**, because that is what lets a reader match it against what they saw. Detail about the *mechanism* does not, beyond the one line that makes the fix intelligible.
- The test is therefore: *is this sentence describing what the user saw, or what the code did?* The first is recognition, the second is archaeology.
- **An explanation of intermittency is symptom detail**, and survives: *"which is why it seemed to come and go — cancel on the frame you started from and nothing went wrong at all"* is what lets somebody recognise a bug they could never reproduce.

**Where a fault could look like data loss, say what was not damaged.** **"No file was ever touched"** is load-bearing: the reader who recognises the symptom immediately wants to know what it cost them. Same principle as saying *destroys* below, pointed the other way — where an entry could alarm, state the bound.

## Where something can be destroyed, say "destroys"

**Euphemism in a destructive entry is not concision.** *"Deleting a system prompt takes the chats held under it with it"* became *"…**destroys** the chats held under it with it"*, and the difference is whether a reader understands what the button does before pressing it rather than after.

This is the one place an entry is allowed to get **longer** under editing, and in the edit that produced this rule it did: what deletion leaves you looking at, and which case stays refused, were *added* — 272 words to 293. Everything else here trims; a destructive action earns its detail, because the cost of a reader misunderstanding it is not a re-read.

## An entry is a selection, not an inventory

**The entry names what changes what someone does. The other true things about the feature go to the README, or nowhere.** Leaving out a fact that is accurate, user-facing and relevant is the normal state of a good entry, not a defect in it.

This needs saying because every other rule here is a filter against *bad* material — internal detail, back-story, diagnostics — and a feature has a dozen facts about it that pass all of them. Each is true, each is user-facing, none is back-story. Nothing so far licenses dropping one, so the entry becomes their union, and it clears every written rule at three times the length it should be.

The difference this corrects is in where the writing starts. Someone who has just implemented the thing writes from the diff, where all twelve facts are equally in view and equally hard-won. The entry wants the other direction: **start from what a user would notice, which is already a sample**, and add only what they would then need. A reader who wants the twelve is a reader who has decided to use the feature, and they are in the documentation by then.

## The measure is whether the section is scannable

**The budget being spent is the reader's attention** (Juha, 2026-09-21). Every rule above is a way of spending less of it, and this is the one to apply where they do not reach: a reader arriving at a release section is looking for the two entries that affect them, and everything that makes the other forty easier to skip past is doing the job.

It also says where to **stop**. An item that is a single clause takes a title and nothing else, because splitting it yields a title and a sentence fragment — two lines spent to learn one thing, which is the failure this rule exists to prevent, arrived at from the other side.

### Line breaks

**One line per bullet**, unwrapped, however long it runs. This is what the fleet's changelogs already do — measured 2026-09-21, `unpythonic` 267 long lines against 93 wrapped, `mcpyrate` 106 against 42 — and the reason to keep to it is that a file wrapped in places and not in others makes the mixture visible where neither style alone would be. A bullet that runs long wants **nesting, not wrapping**: see the section above.

### When a section grows past scanning

A release section long enough that a reader scrolls looking for the entry that concerns them wants its entries **titled**: the bold lead on a line of its own, the prose starting on the next line, indented to the item's content column and with no blank line between them. Markdown folds the two back into one paragraph, so this is a shape the source has and the rendered page does not — which is the point, since the source is where the entries are written and rearranged.

Reach for it when the section is long enough to need it. Raven's 0.2.9 is the case that produced the rule: 139 top-level entries across three sections, at which size a lead that runs into its own prose gives a reader nothing to skim.

**This style is fleet-wide.** What *does* vary per project is release mechanics (tag format, the dev-version suffix), and that lives in the `release` skill, along with the post-release stub. Raven additionally groups entries under component headers, since it ships many apps from one repository; that one is in its own `CLAUDE.md`.
