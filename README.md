# dotclaude

Configuration for [Claude Code](https://claude.com/claude-code), Anthropic's CLI coding agent, as used across my dev machines. It clones into `~/.claude/`, which is where Claude Code looks for its user-level config — so this repo *is* the config directory, not a template that gets copied into it.

Two audiences are served by the same files: a future me setting up a new machine, and anyone curious how a working AI-pair-programming setup is actually wired.

## The AI pair-sysadmin angle

Claude Code reads `CLAUDE.md` as context in every session, so the contents of this directory are not documentation *about* a tool — they are instructions *to* an agent that will act on them. That makes the repo simultaneously machine-readable config and human-readable documentation, and the same file has to work as both.

That dual role drives most of the design decisions here. `CLAUDE.md` stays lean because everything resident in it competes for attention on long sessions; reference material that's only needed sometimes lives in `skills/`, where it loads on demand when the task matches. The split is an attention budget, not a filing convention.

## Why it's public

I keep no private GitHub repos and would like to keep it that way. So everything here is either public or it isn't in git at all — there's no middle tier. That constraint is what shapes the public/local split below: rather than making the repo private to protect a couple of files, the couple of files stay out of the repo.

## The public/local split

Two files are deliberately absent, gitignored, and hand-carried between machines:

- **`SECRET-SAUCE.md`** — a private `CLAUDE.md` fragment. `CLAUDE.md` ends with the line `@./SECRET-SAUCE.md`, which Claude Code resolves as an import at load time. When the file is absent — as on a fresh clone — nothing is imported and Claude Code does not complain.
- **`HARDWARE-NOTES.md`** — GPU models, torch device ordering, benchmark numbers. Per-machine, and nobody else's business.

claude.ai has no import mechanism — its preferences field is one plain text blob — so `CLAUDE_webchat.md` carries the same `@./SECRET-SAUCE.md` placeholder and `scripts/build-webchat.py` expands it into a paste-ready blob.

## Deploying on a new machine

```bash
git clone git@github.com:Technologicat/dotclaude.git ~/.claude
```

Then copy `SECRET-SAUCE.md` and `HARDWARE-NOTES.md` in from an existing machine over whatever private channel you trust. Both are optional — Claude Code starts fine without them.

Restart Claude Code. `statusline.sh` needs `jq`; `scripts/build-webchat.py` needs `xclip`.

For the wider OS-level setup this sits inside — Python toolchain, editor, NVIDIA driver stack, and the rest — see [`NEW-MACHINE-SETUP.md`](NEW-MACHINE-SETUP.md).

Runtime state (`projects/`, `sessions/`, `memory/`, caches) is *not* synced. Each machine accumulates its own. Notably that includes Claude Code's auto-memory: a session on one machine won't know what a session on the other learned yesterday. That's a deliberate tradeoff, not an oversight.

## What's where

| Path | What it is |
|------|------------|
| [`CLAUDE.md`](CLAUDE.md) | Global instructions Claude Code loads every session — who I am, house style, conventions. |
| [`CLAUDE_webchat.md`](CLAUDE_webchat.md) | Backup of the claude.ai userPreferences blob. Its git history *is* the evolution of that wording. |
| [`NEW-MACHINE-SETUP.md`](NEW-MACHINE-SETUP.md) | Sysadmin checklist for bringing up a new Linux dev box. Baseline only — nothing machine-specific. |
| [`GAMING-SETUP.md`](GAMING-SETUP.md) | Steam/Proton, the Input Remapper udev fix, CRT post-processing. Opt-in: not part of baseline setup. |
| [`VKBASALT-SETUP.md`](VKBASALT-SETUP.md) | The vkBasalt build recipe that `GAMING-SETUP.md` leans on. Nontrivial to re-derive; archived deliberately. |
| [`settings.json`](settings.json) | Claude Code settings: permission allowlist, statusline, effort level. |
| [`statusline.sh`](statusline.sh) | Custom status line — venv, host, cwd, model, effort, context usage. |
| [`skills/`](skills/) | On-demand reference material (see below). |
| [`scripts/`](scripts/) | `build-webchat.py` (preferences-blob expander), `run-on-internal-gpu.sh` (hides the eGPU). |
| [`briefs/`](briefs/) | Archived design briefs. |
| `commands/` | Slash commands. Currently empty — the one that lived here became a skill. |

### Skills

[Skills](https://code.claude.com/docs/en/skills) are reference documents with a semantic trigger in their frontmatter: Claude Code loads one when the task at hand matches its description, and otherwise leaves it on disk. They're how this setup keeps deep reference material available without paying for it in every session's context.

- [`ci-setup`](skills/ci-setup/SKILL.md) — GitHub Actions, coverage and Codecov, cibuildwheel, PyPI trusted publishing, and supply-chain hardening (pinning actions to commit SHAs, least-privilege `GITHUB_TOKEN`).
- [`project-setup`](skills/project-setup/SKILL.md) — `pyproject.toml` and the PDM flow, Cython/meson-python builds, lockfile policy, the canonical lint config.
- [`release`](skills/release/SKILL.md) — tagging, CI-driven PyPI publishing, pre/post-release checklists, per-project release title themes.
- [`changelog`](skills/changelog/SKILL.md) — house style for changelog entries. Separate from `release` because entries get written when the bug is fixed, not when the release is cut.
- [`callgraph`](skills/callgraph/SKILL.md) — static call graphs and module dependency graphs via [pyan3](https://github.com/Technologicat/pyan).
- [`cc-log-extract`](skills/cc-log-extract/SKILL.md) — distilling Claude Code session logs into readable Markdown.
- [`unpythonic-macro-testing`](skills/unpythonic-macro-testing/SKILL.md) — testing macro-enabled Python with [unpythonic](https://github.com/Technologicat/unpythonic)'s test framework.

A skill's content lives wherever that content's natural home is. `ci-setup` and `project-setup` are personal sysadmin knowledge, so they're canonical here. `unpythonic-macro-testing` documents the public API of a published library, so it's a pointer — the real reference ships with the library, where it belongs. `cc-log-extract` splits the difference: the workflow recipe is canonical here, the tool it drives lives upstream.

## Runtime state, and the whitelist

Claude Code writes continuously into this directory — sessions, caches, shell snapshots, telemetry. So `.gitignore` is a whitelist: everything at the root is ignored by default and tracked files are opted in one at a time.

The upshot is that when a Claude Code release starts writing some new directory here, it is gitignored automatically and stays out of the repo until someone decides otherwise. A new entry showing up in `git status --ignored` is the safety net working, not a problem to fix.

## Provenance

This repo's design was hashed out in a Claude Code session and reviewed in a claude.ai session; the migration was then executed by Claude Code. The original brief is preserved verbatim in [`briefs/`](briefs/) as a record of the design rationale — including the parts that turned out to be wrong. Future briefs land alongside it.

The wider context for how these projects are built — the AI-collaboration ethnography, and the glossary of coined terms that the house style leans on — is [substrate-independent](https://github.com/Technologicat/substrate-independent).
