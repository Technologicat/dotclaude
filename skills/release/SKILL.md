---
name: release
description: How releases are cut in this fleet — git tag format (varies by project; check before tagging), the CI-driven PyPI publishing flow via trusted publishing, the pre-release checklist (local file-path deps break sdists), the post-release version-bump pattern, and the per-project release title themes. Use when cutting or preparing a release, tagging a version, drafting GitHub release notes, or bumping a version after a release. For the wording of CHANGELOG.md entries, see the `changelog` skill.
---

# Cutting a release

**Check the tag format first.** It varies by project — some use `vX.Y.Z` (pylu), others bare `X.Y.Z` (mcpyrate). Run `git tag --list` and match what's already there. Guessing wrong creates a tag that CI won't fire on.

**Publishing is CI-driven.** GitHub Actions publishes to PyPI on tag push, via trusted publishing (OIDC — no API tokens). There is no manual `twine upload` step. Tag, push, create the GitHub release.

## Pre-release

Check `pyproject.toml` for local file-path dependencies (`file:///...`). PyPI rejects these in sdists, and the failure comes late — at upload, after the build has already run.

**Pick the release title** (see themes below), then close the changelog's in-progress section with it. The heading carries version, date and title:

```markdown
**2.2.0** (12 May 2026) — *"Hail Eris"* edition:
```

...replacing the stub heading it grew under:

```markdown
**2.2.1** (in progress):
```

The same title goes on the GitHub release, prefixed with the project name — `mcpyrate 4.2.0 — "X marks the spot"`.

### Release title themes

Each project draws its release titles from its own well:

- **mcpyrate** — ships and pirates
- **unpythonic** — meta-commentary, discordian
- **pyan3** — cartography

Hotfix and patch releases have gone out untitled (`**4.1.1** (8 May 2026) - hotfix:`, released as plain "Version 4.1.1"), so a title doesn't appear to be mandatory for those — but the pattern is observed, not stated policy. Ask if unsure.

## Post-release

Bump the version to `X.Y.Z-dev` in source, and add the next changelog stub — "(in progress)", with "*No user-visible changes yet.*" under it. Commit and push.

Do this immediately after tagging, rather than at the start of the next release: it means the next bugfix already has somewhere to write its changelog entry, which is what keeps entries getting written while the context is fresh instead of reconstructed from `git log` months later.

## Changelogs

Entry wording, scope, and the "is this even user-visible?" test are in the `changelog` skill. The release-time touchpoints are the two above: retitle the in-progress section before tagging, open a fresh stub after.
