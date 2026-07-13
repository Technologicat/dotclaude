---
name: release
description: How releases are cut in this fleet — git tag format (varies by project; check before tagging), the CI-driven PyPI publishing flow via trusted publishing, the pre-release checklist (local file-path deps break sdists), the post-release version-bump pattern, and the per-project release title themes. Use when cutting or preparing a release, tagging a version, drafting GitHub release notes, or bumping a version after a release. For the wording of CHANGELOG.md entries, see the `changelog` skill.
---

# Cutting a release

**Check the tag format first.** It varies by project — some use `vX.Y.Z` (pylu), others bare `X.Y.Z` (mcpyrate). Run `git tag --list` and match what's already there. Guessing wrong creates a tag that CI won't fire on.

**Publishing is CI-driven.** GitHub Actions publishes to PyPI on tag push, via trusted publishing (OIDC — no API tokens). There is no manual `twine upload` step. Tag, push, create the GitHub release.

**Pre-release checklist:** check `pyproject.toml` for local file-path dependencies (`file:///...`). PyPI rejects these in sdists, and the failure comes late — at upload, after the build has already run.

**Post-release:** bump the version to `X.Y.Z-dev` in source, add a changelog stub with "(in progress)" and "*No user-visible changes yet.*", commit and push. Doing this immediately means the next bugfix has somewhere to write its entry.

**Release title themes**, by project:

- **mcpyrate** — ships and pirates
- **unpythonic** — meta-commentary, discordian
- **pyan3** — cartography

## Changelogs

Entry wording, scope, and the "is this even user-visible?" test are in the `changelog` skill. The release-time touchpoints are:

- Before tagging: make sure the in-progress section is complete and retitled from "(in progress)" to the version being released.
- After tagging: add the next "(in progress)" stub, per the post-release step above, so the next bugfix has somewhere to write its entry.
