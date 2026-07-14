---
name: release
description: How releases are cut in this fleet — git tag format (varies by project; check before tagging), the CI-driven PyPI publishing flow via trusted publishing, the pre-release checklist (local file-path deps break sdists), the post-release version-bump pattern, and the per-project release title themes. Use when cutting or preparing a release, tagging a version, drafting GitHub release notes, or bumping a version after a release. For the wording of CHANGELOG.md entries, see the `changelog` skill.
---

# Cutting a release

**Check the tag format first.** It varies by project — some use `vX.Y.Z` (pylu), others bare `X.Y.Z` (mcpyrate). Run `git tag --list` and match what's already there. Guessing wrong creates a tag that CI won't fire on.

**Publishing is CI-driven.** GitHub Actions publishes to PyPI on tag push, via trusted publishing (OIDC — no API tokens). There is no manual `twine upload` step. Tag, push, create the GitHub release.

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

A titled release draws its name from the project's own well:

- **mcpyrate** — ships and pirates
- **unpythonic** — meta-commentary, discordian
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

## Changelogs

Entry wording, scope, and the "is this even user-visible?" test are in the `changelog` skill. The release-time touchpoints are the two above: retitle the in-progress section before tagging, open a fresh stub after.
