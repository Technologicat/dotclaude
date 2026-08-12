---
name: monthly-report
description: Build a monthly (or any date-range) cross-project activity report from Claude Code session logs — scope the window, extract per-project digests, verify releases against git tags, synthesize, archive the digests, export for email. Use when the user says "monthly activity report time", "pull the chatlogs and check what we've been building", or asks for a period summary of work across the fleet.
---

# Writing a monthly activity report

An executive summary of what the whole project fleet built during a period, drafted
from Claude Code session logs. The audience is colleagues and management who don't
know the fleet — they read it to see what a month of work produced, so every project
gets a one-line gloss of what it *is* before any detail about what happened to it.

Extraction mechanics (invocation, options, model stamps) are in the `cc-log-extract`
skill; this skill owns the report pipeline around them.

## Where reports live

Machine-local and deliberately not recorded here — `~/.claude` is a public repo.
The output directory is in `SECRET-SAUCE.md` (imported into every session) under
*Monthly activity reports*, with auto-memory as a secondary hint. If neither has it,
ask.

## The pipeline

### 1. Scope the window

The report covers **session content**, not the calendar month, and the window is
bounded by its neighbours: it opens where the *previous* report's coverage line closed
and closes where the *next* one opens. Read both neighbours' coverage lines before
picking the bounds. For the usual case — the newest month, no next report — the upper
bound is the last session before today; for a back-fill or a re-draft of an older
month, it is the following report's start, and the windows must abut without gap or
overlap.

Three things make the window ragged, and each needs a deliberate call:

- **Boundary spanners.** A file's mtime is its *last* turn, so an mtime filter selects
  sessions by where they **ended**. Two consequences, both one-directional:
  - A session begun in April and resumed in May carries a May mtime and April content.
    The converse cannot occur — mtime never precedes the last turn — so the risk is
    pulling in earlier content, never missing later content.
  - mtime is local time; the `timestamp` fields inside the log are UTC. At UTC+3 a
    session ending 23:30 on the 31st has an mtime on the 1st of the next month, so it
    drops out of the window on a strict filter.

  Widen the mtime bounds by a day at each end, then open the first and last
  `timestamp` in every boundary file and assign it deliberately.
- **Logs are machine-local, and nothing syncs them.** `~/.claude/projects/` holds only
  the sessions run on *this* box, so a period spanning two machines needs a digest set
  from each. Run step 2 on both, then copy the `YYYY-MM/` folder across by hand; the
  report gets written wherever both sets have landed.

  Merge at the **digest** layer, not the report layer. Extraction is inherently
  machine-local; synthesis is the step that needs everything at once, and the
  cross-cutting sections are exactly what two separately-written reports cannot see.
  Raw logs stay where they are — synthesis never reads them.
- **A session still running when you draft.** A long-lived session — the kind a big
  sprint produces, weeks of turns in one file — can be live at the moment of writing,
  so the window closes at its last recorded turn: a **mid-session, mid-day boundary**,
  not the tidy day boundary the other cases give you.

  That is correct, and it needs to be *written into the coverage line* — timestamp,
  session UUID, and which machine — because next month's window opens **inside the same
  file**. A reader who assumes one file belongs to one month will either double-count
  its early turns or drop them. Name any work that was mid-flight at the cut, too, so
  the next report knows it is picking up a thread rather than starting one.

Bounds widened by a day at each end, per the spanner note above; the extra files get
resolved by reading their timestamps, not by trusting the filter:

```bash
find ~/.claude/projects -name '*.jsonl' \
  -newermt '2026-04-30' ! -newermt '2026-06-02' \
  -printf '%TY-%Tm-%Td %TH:%TM  %10s  %p\n' | sort
```

### 2. Extract one digest per project

The top-level dirs under `~/.claude/projects/` are the source of truth for what was
worked on — not the fleet list in `CLAUDE.md`. One-off projects show up there and
deserve a section (May 2026 had `geography-figures`, which is in no fleet list).

**A project dir names a working directory, not a project**, so the mapping to report
sections is neither one-to-one nor stable. Resolve it before extracting:

- **One project, several dirs.** A checkout at two paths gets two dirs; a renamed
  directory leaves the old one behind holding all the history under the old name
  (chandra's early work sits under `imagegen-metadata-tools`). Both feed one section —
  concatenate the sessions rather than reporting the project twice.
- **Dirs that are not projects.** Scratchpad and `/tmp` working directories appear
  alongside the real ones. Skip them.

Run `cc-log-extract.py` once per project, that project's sessions in chronological
order, `--timestamps`, default `--tools summary`. Subagent transcripts live at
`<session-uuid>/subagents/agent-*.jsonl`; include or skip them deliberately.

The script lives in the **substrate-independent** repo, not in this one:

```
~/Documents/koodit/substrate-independent/scripts/cc-log-extract.py
```

So a fix to it lands there — pulling `~/.claude` does not bring it. The `cc-log-extract`
skill has the options and the model-stamp semantics.

### 3. Verify the releases against git

The *Releases shipped this period* section is the one part made of hard artifacts, so
don't take it from the session narrative — a release discussed in a session may not
have been cut, and one cut outside a session won't appear at all. Read the tags:

**Un-stale the checkouts first** — a local clone is a cached view, and it will happily
report last month's state. `~/.claude/scripts/fleet-pull.sh` does the whole fleet in
one go; its plain `git fetch --prune` brings new tags along with the branch. Two
conditions on using it:

- **No other Claude Code session running.** It stashes tracked changes and
  fast-forwards working trees, which is not something to do underneath another
  session's work.
- **Fleet projects only.** Its project table is the fleet list, so a one-off project
  that earned a report section (`geography-figures`) needs its own `git fetch`.

Then read the tags, whole list, and pick out the window's dates:

```bash
git -C ~/Documents/koodit/<project> tag --list \
  --sort=creatordate --format='%(creatordate:short)  %(refname:short)'
```

Don't `head` it — that answers "what shipped most recently" rather than "what shipped
during the window", and so returns the wrong tags for any month but the newest.

### 4. Synthesize

For a light month, read the digests directly. For a heavy one — raven's June digest
was 1.1 MB — fan out one subagent per digest, each returning a structured
"what was built" summary (deliverables, decisions, releases, per-session gist), then
write the report from those. That keeps the orchestrator's context clean enough to see
the cross-cutting work.

**Cross-cutting sections have to be assembled deliberately.** A per-project digest
cannot see that the same CI hardening pass touched all nine repos; only the
orchestrator, holding every summary at once, can.

**The digests are the evidence.** Where the report asserts *why* something was done,
that reason must be traceable to a digest or to the artifact itself. An unsourced
"which enabled…" or "this was needed because…" is where fabrication enters a document
nobody downstream can check — cut it, or go read the commit.

### 5. Archive the digests

Write them to `<report-dir>/YYYY-MM/<project>.md`, beside the report. The report
asserts what was built; the digests are the backing detail, and next month's report
often needs to look back at them.

**Always suffix the digest with the machine it came from** — `raven-$(hostname).md`,
unconditionally, even for a period that only ever ran on one machine. The machine
doing the extraction cannot know whether the other one also touched that project, so
a conditional rule is undecidable precisely when it matters: the two folders have to
merge without collisions, and a plain `raven.md` from each machine silently loses one.
The attribution survives in the archive as a free side effect.

### 6. Export for email (on request)

Outlook doesn't parse Markdown, so the report gets pasted in as rich text:

```bash
pandoc activity-report-2026-06-v0.md -o activity-report-2026-06-v0.docx   # or .odt
```

Plain invocation, no flags — the export exists to survive a copy-paste, not to carry
house styling. (`--reference-doc=template.docx` is the hook if that ever changes.)

## House format

```markdown
# Activity Report — June 2026

*Covers 2026-06-03 through 2026-06-29. Executive summary across active projects.
Drafted from Claude Code session logs; all work this period ran on Opus 4.8.*

---

## Releases shipped this period
                                  every release in the window, shipping projects only

## <project> — <one-line gloss of what the project is>
                                  opens with this project's release, or "No release
                                  this period"; only projects that saw work appear
### <component>                  (only where a project needs the breakdown)

## Cross-cutting: <named theme>   (e.g. fleet-wide CI supply-chain hardening)

## Cross-cutting themes
```

- **One section per active project** — the primary structure. Ordered by how much
  happened, each titled with a gloss of what the project *is*, and the dominant project
  of the period named as such in its opening line.

  **A project that saw no work gets no mention.** The audience is colleagues reading
  for what the month produced; a roll-call of untouched projects is noise to them.
  Absence in the report means absence of work, and that is the only thing it means.
- **Each project section opens with its releases** — hard artifact first, then the
  narrative of the work. For an active project that shipped nothing, say so ("No
  release this period"), so a reader looking at a substantial section can tell a
  quiet month from an omission.
- **Coverage line** (italic, under the title): the real date range from session
  contents, and the model(s) the work ran on. `cc-log-extract`'s model stamps give
  you the latter.
- **Releases shipped this period**, up top, is the executive skim: every release in
  the window, one line each, so a reader who wants only the artifacts never scrolls.
  It lists **only projects that actually shipped** — the per-project sections carry
  the "no release this period" notes, and repeating them here would rebuild the
  roll-call the previous rule cuts. The overlap with the project sections is
  deliberate: the two answer different questions.
- **Cross-cutting themes** at the end: three to five numbered items, each naming
  something the per-project sections can't say on their own.

## Style

Concise with good coverage — the report's length follows how much got done, so don't
target a line count. Cut back-story, never information. This is the `changelog` skill's
density rule, and the rest of that skill's guidance transfers directly:

- **Short items.** A bullet says what was built and what it does; the diagnostic trail
  stays in the commit message.
- **Nest subordinate detail.** A caveat or consequence belonging to an item goes in a
  child bullet, not flattened into a sibling (which reads as an independent
  deliverable) or crammed into the lead sentence (which buries it).

The failure this prevents: a report padded to look substantial, which the reader then
skims — and a report compressed to a fixed length, which drops real deliverables in a
heavy month. Density is the constraint; length is an output.

Assume no fleet knowledge. Spell out what a project is, what a component does, and why
a release mattered. Identifiers in backticks are fine — the audience is technical, just
not familiar with these particular repos.

## Versioning

`activity-report-YYYY-MM-vN.md`, starting at `v0` for the draft. Later versions are the
user's own edits; write `v0` and stop there unless asked to revise. Exports sit beside
the `.md` with the same stem.
