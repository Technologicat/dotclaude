---
name: cc-log-extract
description: Extract readable conversation turns from Claude Code JSONL session logs (the files under ~/.claude/projects/<project>/). Use when summarizing past sessions, writing a monthly/weekly activity report ("what did we build", "pull the chatlogs"), reviewing how a feature was implemented across a session, doing AI pair-programming ethnography, or tracking which model produced which turns. Strips tool-I/O noise and emits Markdown with model stamps.
---

# Extracting Claude Code session logs

Claude Code stores every session as a JSONL transcript under
`~/.claude/projects/<munged-project-path>/<session-uuid>.jsonl`. The project dir
name is the absolute cwd with `/` **and `.`** both replaced by `-` — so
`/home/me/.claude` becomes `-home-me--claude` (note the doubled dash where the dot
was), and `/home/me/Documents/koodit/raven` becomes
`-home-me-Documents-koodit-raven`. Don't reconstruct the name by hand; `ls` the
`projects/` directory and match.

Each line is one record: `user` / `assistant` messages, plus harness records
(`ai-title`, `permission-mode`, `file-history-snapshot`, `system`, …). Assistant
content is a list of `text` / `thinking` / `tool_use` blocks; user content is a
string or a list that may include `tool_result` blocks. Raw, these files are mostly
tool-I/O noise — useless to read directly.

Subagent transcripts live beside the session that spawned them, at
`<session-uuid>/subagents/agent-<id>.jsonl` — a directory named after the session
UUID, sibling to the session's own `.jsonl`.

`cc-log-extract.py` distills them into readable Markdown: HUMAN + CC prose
turns, tool calls collapsed to one-liners (`[Edit: foo.py]`, `[Bash: pytest]`),
`thinking` and `tool_result` bodies dropped, consecutive duplicates merged, and
a **model stamp** per session (single-model → `Model: Opus 4.7`; multi-model →
per-turn-range breakdown + raw API strings).

## The tool — single source of truth

The script lives in the **substrate-independent** repo (it has its own test
suite there — `scripts/tests/test_cc_log_extract.py`); do not fork or copy it,
just call it where it lives:

```
~/Documents/koodit/substrate-independent/scripts/cc-log-extract.py
```

If that path is missing (repo not cloned on this machine), say so rather than
reimplementing.

```
python3 .../cc-log-extract.py SESSION.jsonl [MORE.jsonl ...] -o out.md [options]
```

Key options:
- `--tools summary` (default) one-liner per tool call · `edits` show Edit/Write
  content, omit Reads (light code-review mode) · `full` truncated tool input ·
  `none` prose only
- `--timestamps` — date+time on every turn
- `--per-turn` — tag each CC turn inline with its model (`*(opus-4-7)*`)

Multiple session files concatenate into one document — pass a whole project's
sessions at once.

## Recipe: monthly (or any date-range) activity report

1. **Find the sessions for the window.** mtime is a good first cut, but a
   session can span a month boundary — a late-April session resumed in May has
   a May mtime but April content, and vice versa. Filter by mtime, then
   sanity-check the boundary files by reading the first/last `timestamp` inside
   them. Subagent transcripts live under `<uuid>/subagents/agent-*.jsonl`;
   include or skip them deliberately.

   ```bash
   find ~/.claude/projects -name '*.jsonl' \
     -newermt '2026-05-01' ! -newermt '2026-06-01'
   ```

2. **Group by project** (the top-level dir under `projects/`) and run the
   extractor once per project, passing that project's sessions in chronological
   order, to `-o /tmp/<project>.md`. Use `--timestamps`; default `--tools
   summary` is right for "what was built" (the tool one-liners show the shape of
   the work without the noise). `ai-title` records give each session a
   human-readable title for free.

3. **Synthesize.** For a light month, read the digests directly. For a heavy one
   (a multi-MB project digest), fan out one subagent per project digest — each
   returns a structured "what was built" summary (deliverables, decisions,
   releases, per-session gist) — then write the report from those. This keeps
   the orchestrator's context clean.

4. **Archive the per-project digests** alongside the report, in a dated subfolder
   (`YYYY-MM/<project>.md`). They are the readable backing detail: the report
   asserts what was built, the digests are the evidence, and next month's report
   often needs to look back at them.

### House format for the report

```markdown
# Activity Report — June 2026

*Covers 2026-06-03 through 2026-06-29. Executive summary across active projects.
Drafted from Claude Code session logs; all work this period ran on Opus 4.8.*

---

## Releases shipped this period

## <project> — <one-line description of what it is>
### <component>            (only where a project needs the breakdown)

## Cross-cutting: <named theme>     (e.g. fleet-wide CI supply-chain hardening)

## Cross-cutting themes
```

- **Coverage line** (italic, under the title): the actual date range covered, and
  the model(s) the work ran on. The date range comes from the *contents* of the
  sessions, not the calendar month — say what was really covered.
- **Releases shipped this period** goes first: it's the part with hard artifacts.
- **One section per active project**, titled with a short gloss of what the project
  *is* — the report is read by people who don't know the fleet.
- **Cross-cutting sections** for work that spanned projects (a fleet-wide CI change,
  a convention rollout). These are the ones a per-project digest can't see, so they
  have to be assembled deliberately.

**Versioning:** `activity-report-YYYY-MM-vN.md`, starting at `v0` (draft) and
iterating as the user revises. `.docx`/`.odt` exports may sit beside the final `.md`.

**Where reports live** is machine-local and deliberately not recorded here (this repo
is public). It's in auto-memory; if it isn't, ask.

## Other uses

- **"How did we build X?"** — extract the relevant session with `--tools edits`
  to see the actual diffs inline.
- **Ethnography / field notes** — `--no-tools` for pure HUMAN↔CC dialogue; the model
  stamps let you attribute behavior to a specific model version.

  The stamp groups by `family-major-minor`, folding a bare identifier
  (`claude-opus-4-7`) together with a dated pin of the same version
  (`claude-opus-4-7-20260416`) — under the current naming scheme those are the same
  model, and splitting them would fragment the attribution for no reason. Note this is
  a property of the *present* scheme rather than a law: under older naming, two dated
  releases could share family-major-minor and genuinely differ (the `3-5-sonnet` pair
  of 2024). The raw API strings are preserved verbatim in the header precisely so that
  if the distinction ever matters, nothing has been thrown away.
