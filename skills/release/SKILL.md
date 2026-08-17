---
name: release
description: How releases are cut in this fleet — git tag format (varies by project; check before tagging), the CI-driven PyPI publishing flow via trusted publishing, the pre-release checklist (local file-path deps break sdists), the post-release version-bump pattern, and the per-project release title themes. Use when cutting or preparing a release, tagging a version, drafting GitHub release notes, or bumping a version after a release. For the wording of CHANGELOG.md entries, see the `changelog` skill.
---

# Cutting a release

**Check the tag format first.** It varies by project — some use `vX.Y.Z` (pylu), others bare `X.Y.Z` (mcpyrate). Run `git tag --list` and match what's already there. Guessing wrong creates a tag that CI won't fire on.

**Make it an annotated tag**, with the GitHub release title as its message:

```bash
git tag -a v2.4.0 -m 'unpythonic 2.4.0 — "Tis but a scratch"'
```

Fleet-wide, and the reason is forward-looking rather than current: **only annotated tags can be GPG-signed**, so signing release tags — the natural next step after SHA-pinning actions and least-privilege workflow tokens — needs them. Retrofitting would mean replacing tags that are already published, which is the awkward case. Annotated tags also carry their own message, tagger and date, independent of the commit, so `git tag -n` lists the release names.

Existing tags are mixed: the ones made by hand (command line, later Magit, which annotates by default) are annotated; some agent-made ones are lightweight. Do not go back and convert a published tag. Re-pushing it re-fires the tag workflow, PyPI rejects the duplicate version, and a cosmetic inconsistency becomes a red release run.

**Publishing is CI-driven.** GitHub Actions publishes to PyPI on tag push, via trusted publishing (OIDC — no API tokens). There is no manual `twine upload` step. Tag, push, create the GitHub release.

**The `publish` job lives inside `.github/workflows/ci.yml`, not in a workflow of its own.** It is a job named `publish`, gated on an `if:` over `github.ref` and taking the built dist from `build-dist` as an artifact. Listing workflow *filenames* therefore suggests the fleet has no publishing at all — a wrong conclusion that is easy to reach and alarming when reached. Grep for `publish:` or `id-token` instead.

**How wide the tag gate is varies by project, in step with the tag format.** `v*`-tagging projects gate on `refs/tags/v` (unpythonic, pyan, pylu); bare-`X.Y.Z` projects gate on `refs/tags/` and therefore **publish on any tag at all** (mcpyrate, chandra). On those two, a tag pushed for some unrelated purpose is a release. Raven matches `v*` but has no `publish` job — it is an application, not a PyPI package.

## Pre-release

**Tag only once CI is green on the exact commit you intend to tag.** Push the release commit, wait for the run to pass, *then* tag and push the tag. Never tag and push in one motion on the strength of a local test run.

The failure this prevents: a red tag run means the publish never happens, and recovering costs either force-moving a public tag or burning the version number entirely. On an ordinary push a red CI is cheap — fix it and push again. On a tag it is not, and the asymmetry is the whole reason the rule exists. (A local suite passing is not the same as CI passing: CI also lints.)

Check `pyproject.toml` for local file-path dependencies (`file:///...`). PyPI rejects these in sdists, and the failure comes late — at upload, after the build has already run.

**Settle the version number first — the stub's is provisional.** The in-progress stub was opened right after the last release, when the only guess available was "next patch". What it actually becomes depends on what landed in it, per semver:

```markdown
**2.2.1** (in progress):        ← stub, opened after 2.2.0 shipped
```

becomes `2.2.1` if only fixes landed, `2.3.0` if features did, or `3.0.0` on a breaking change. Renumber the heading to match reality; don't inherit the guess.

**Then close the section with version, date and — for a feature release — a title:**

```markdown
**2.3.0** (12 May 2026) — *"Hail Eris"* edition:
```

The same title goes on the GitHub release — in whatever shape that project uses; see "Heading formats vary by project" below.

**Patch and hotfix releases go out untitled.** Titles are for minor and major releases. A patch keeps the plain form in both places:

```markdown
**4.1.1** (8 May 2026) - hotfix:
```

...released on GitHub as simply `Version 4.1.1`.

### Release title themes

**The name puns on what the release actually did.** That is the part to get right; the theme only
says which well to draw the pun from. `mcpyrate` 4.2.0 "X marks the spot" was the release that added
end-to-end source *locations*; 4.3.0 "Weigh anchor" was the one where the expander had been unable to
import at all, so it never left port; `unpythonic` 0.15.0 "We say 'howdy' around these parts" was the
release that introduced *dialects*. A name that fits the theme but not the content is the failure
mode to avoid — it reads as decoration.

**Most of them are quoted lines**, not topical nods — a catchphrase the source is known for, which
happens to pun on the release. *"Just one more thing"* is Columbo's; *"'Tis but a scratch"* is the
Black Knight's; *"Maybe a slice?"* is what a caddie in *Everybody's Golf 4* says on practically every
putt, which is the part that makes it land for anyone who played it. A line beats a topic word,
because a reader who knows it hears the delivery.

The exception worth recognizing is a phrase that has become part of the fleet's own vocabulary.
*"Six impossible things before breakfast"* is the White Queen's line, but `CLAUDE.md` states it as
the ambition level for the projects, so the 2.0.0 title is quoting the house standard rather than
reaching for Carroll. Those work for a different reason and do not need the link.

**Link the reference from the title itself**, on the referenced words, where there is one to link.
This is long-standing in `unpythonic` and is what makes the deep cuts land for a reader who does not
recognize them: `*"Maybe a slice?"* [edition](.../Everybody%27s_Golf_4)`, `*["Super Syntactic
Fortress MACROS"](.../Super_Dimension_Fortress_Macross) edition*`. Check the URL resolves before
committing it.

A titled release draws its name from the project's own well:

- **mcpyrate** — ships and pirates
- **unpythonic** — cultural references and wordplay of any provenance, chosen to pun on the release.
  The register is wide and the deep cuts are welcome: anime (*"Super Syntactic Fortress MACROS"*, for
  the release that introduced `unpythonic.syntax`), Discordianism (*"Hail Eris"*), Carroll (*"Six
  impossible things before breakfast"*, *"Through the looking glass"*), Hofstadter (*"Metamagical
  engineering"*), film (*"The hunt for missing operators"*), rhythm games (*"573 combo!"*, Konami's
  own number), the London Underground (*"Mind the gap"*), plain puns (*"Cat-hedral"*,
  *"Listhonkell"*), and self-referential jokes about the versioning itself (*"0.10.0 is more than
  0.9.∞"*). **A gag may run across consecutive releases** — 0.10.1 *"Just one more thing"* (Columbo)
  became 0.10.2 *"Just a few more things"*, then deflated into 0.10.3 *"Small fixes"*.
- **pyan3** — cartography
- **chandra** — its decipherment/astronomy palette: *reading what's present but unseen*. (Hence `Earthshine` — Earth's reflected light revealing the moon's dark limb. The palette is described in chandra's own `CLAUDE.md` under "Voice and naming", and covers component names too: `rosetta`, `concordance`, `palimpsest`.)
- **raven** — none. It's an evolving research prototype; releases are plain (`Raven 0.2.7`).

### Heading formats vary by project — copy the last release

Like the tag format, the changelog heading and the GitHub release title differ across
projects. Don't apply another project's shape from memory; open the repo's `CHANGELOG.md`
and its previous GitHub release, and match what's there. Two live examples:

```markdown
**2.2.0** (12 May 2026) — *"Hail Eris"* edition:     unpythonic, mcpyrate
## 0.2.0 — 2026-06-16                                chandra (ISO date, ## heading)
```

and on GitHub, `mcpyrate 4.2.0 — "X marks the spot"` (project name prefixed) versus
chandra's `0.2.0 — Earthshine` (not prefixed).

## Post-release

Bump the version to `X.Y.Z-dev` in source, and add the next changelog stub — "(in progress)", with "*No user-visible changes yet.*" under it. Commit and push.

Do this immediately after tagging, rather than at the start of the next release: it means the next bugfix already has somewhere to write its changelog entry, which is what keeps entries getting written while the context is fresh instead of reconstructed from `git log` months later.

## Sister projects release together

`mcpyrate` and `unpythonic` are coupled: `unpythonic.syntax` is built on the expander, and
`unpythonic` declares a `mcpyrate` dependency. When a change touches both — a Python version
bump being the usual case — hold both tags until the pair has been verified working *against
each other*, then release them together.

Releasing the dependency alone publishes a version its sibling has not been tested against, and
whoever installs the new `mcpyrate` gets it paired with the old `unpythonic` by default. The
verification that matters is running `unpythonic`'s suite against the `mcpyrate` about to ship,
not each project's suite in isolation.

## Dropping a Python version: two releases, not one

When a Python version reaches end of life, the floor rises in a *separate, later* release than
whatever else is in flight. Ship the current work with the old floor intact, then drop the floor on
its own afterwards.

The point is to give users a version they can upgrade to without also having to upgrade their
interpreter. Bundling the two means anyone stuck on the old Python cannot take the fix at all, which
is precisely the population most likely to be stuck on old infrastructure generally.

Live case: **Python 3.10 reaches EOL on 2026-10-31.** The three AST users (`mcpyrate`, `unpythonic`,
`pyan`) are getting Python 3.15 support now, and each keeps `>=3.10` through that release. The
floor moves to 3.11 in a following release, after the EOL date. 3.15 final is expected around the
same time, so expect the two to be adjacent — resist the temptation to merge them.

## Changelogs

Entry wording, scope, and the "is this even user-visible?" test are in the `changelog` skill. The release-time touchpoints are the two above: retitle the in-progress section before tagging, open a fresh stub after.
