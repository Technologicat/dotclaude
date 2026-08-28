---
name: cc-log-extract
description: Extract readable conversation turns from Claude Code JSONL session logs (the files under ~/.claude/projects/<project>/). Use when summarizing past sessions ("what did we build", "pull the chatlogs"), reviewing how a feature was implemented across a session, doing AI pair-programming ethnography, or tracking which model produced which turns. Also when the log is being consulted as a *record* rather than read as prose: recovering what a compaction dropped ("what were we about to do", a TODO lost across a seam), or timing something that already happened ("how long did that actually take", checking an estimate against the commit that closed it). Strips tool-I/O noise and emits Markdown with model stamps. For a monthly activity report, see the `monthly-report` skill, which drives this one.
---

# Extracting Claude Code session logs

Claude Code stores every session as a JSONL transcript under
`~/.claude/projects/<munged-project-path>/<session-uuid>.jsonl`. The project dir
name is the absolute cwd with `/`, `.` **and `_`** all replaced by `-` — so
`/home/me/.claude` becomes `-home-me--claude` (note the doubled dash where the dot
was), and `/home/me/Documents/proj_name/raven` becomes
`-home-me-Documents-proj-name-raven`. The munging is lossy and not invertible: don't
reconstruct the name by hand, `ls` the `projects/` directory and match.

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
- `--timestamps` — date+time on every turn, as local time with the UTC offset
  (`2026-06-06 01:22:11 +03:00`). The log itself records UTC; the offset is what
  lets a digest still be read in another zone, or months later
- `--per-turn` — tag each CC turn inline with its model (`*(opus-4-7)*`)

Multiple session files concatenate into one document — pass a whole project's
sessions at once.

## Uses

- **Monthly activity report** — the whole pipeline (scoping the window, one digest
  per project, verifying releases against git tags, synthesis, archiving, export)
  is in the `monthly-report` skill. Start there; this skill covers only the
  extraction step it calls.
- **"How did we build X?"** — extract the relevant session with `--tools edits`
  to see the actual diffs inline.
- **Recovering what a compaction dropped.** A summary keeps what mattered to the
  summarizer, and an unplanned one — the context filling mid-item, the handover
  improvised — keeps rather less. The log has every turn. Extract from the last
  clean point to the seam and read what was outstanding: the "next we should…"
  that never reached a file, a TODO agreed in conversation, a decision that
  produced no diff. **The compacted session can do this to itself**, which is the
  case worth knowing about: its own transcript is still on disk under its own
  UUID, and it is the only copy of what it has just forgotten.

  This should be rare. It is the failure mode the "leave the last turn fit to be
  compacted" rule exists to prevent, and reaching for the log means that rule was
  not applied in time. Worth doing anyway when it happens — the alternative is
  re-deriving the same decisions, differently, without knowing you are.

- **Timing something that already happened.** Every record carries a `timestamp`
  (UTC, ISO-8601), so the log answers questions the conversation no longer can:
  when a thing was said, how long it took, what preceded it.

  The estimate-versus-actual check is the useful instance. An estimate stated in a
  message has a timestamp; the commit that closed it has one too, from
  `git log --format=%ad --date=iso-strict`. Neither party reconstructs elapsed
  time reliably afterwards, and the two records settle it in one command. (Live
  case, Raven 2026-08-28: a GUI sweep estimated at "an hour or so" was committed
  20.4 minutes later.)

  **For timing, read the raw JSONL rather than the extracted Markdown.** The
  extractor is built for reading — it merges consecutive turns and drops tool
  bodies — and `--timestamps` stamps what survives that, which is the wrong grain
  when the question is when a particular tool call ran. `json.loads` per line and
  pick the `timestamp` off the records you want.

- **Ethnography / field notes** — `--no-tools` for pure HUMAN↔CC dialogue; the model
  stamps let you attribute behavior to a specific model version.

  The stamp groups by `family-major-minor`, folding a bare identifier
  (`claude-opus-4-7`) together with a dated pin of the same version
  (`claude-opus-4-7-20260416`) — under the current naming scheme those are the same
  model, and splitting them would fragment the attribution for no reason.

  Note this is a property of the *present* naming scheme rather than a law. Under
  older naming, two dated releases could share `family-major-minor` and still be
  genuinely different models — `claude-3-5-sonnet-20240620` and
  `claude-3-5-sonnet-20241022` were distinct models, and there the date was the *only*
  thing telling them apart. (Both appear in Anthropic's
  [model deprecations list](https://platform.claude.com/docs/en/about-claude/model-deprecations),
  which is the place to check identifiers of this kind.) If identifiers of that shape
  ever turn up in the logs, the stamp will merge them and be wrong to do so.

  This is why the raw API strings are preserved verbatim in the header: the grouping is
  a convenience, the raw strings are the record, and nothing has been thrown away if
  the distinction turns out to matter.
