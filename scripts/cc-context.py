#!/usr/bin/env python3
"""How full is this Claude Code session's context window?

Why this exists: the figure a session can see for itself is *not* the answer. `total_tokens` in the
transcript resets to its ceiling at the start of every user message and ticks down through that turn's tool
calls, so a reading late in a long session can be *higher* than one from early in it. Reading it as
"context left" produces confident advice that is wrong by two orders of magnitude — a live case reported
"context is at roughly 0.2%, so there is no overrun risk" while the window was 46% full.

The real figure is on disk, in the session's own log, and is the sum of three fields:

    input_tokens + cache_creation_input_tokens + cache_read_input_tokens

All three, because nearly all of the prompt is `cache_read_input_tokens` — reading `input_tokens` alone
returns something like `2`, which looks like an answer and is not.

This was a snippet in `CLAUDE.md` before it was a script, which is the same mistake `ci-watch` was written
to fix: a fenced code block is invisible to every sweep that would keep it correct, and a wrong answer here
looks exactly like a right one.

**It lags, but by an absolute amount rather than a proportional one.** The newest record is the prompt of
the last completed API round, so the error is whatever has been added since — the current message plus
whatever has been written this turn, a few thousand tokens. That is a rounding error against a large window
at any fill level. It is worth a second thought only right after ingesting something big (a large file read,
a subagent's report), and then the fix is to run it again a round later. The age of the record is printed
so that this is visible rather than assumed.
"""

import argparse
import datetime
import json
import pathlib
import sys

PROJECTS = pathlib.Path.home() / ".claude" / "projects"

# The fields that together make up the prompt. Named here rather than inline because the whole point of the
# script is that this list is easy to get wrong.
PROMPT_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

# The window a model id implies. The long-context variants say so in the id itself, as a `[1m]` suffix;
# everything else is Claude's standard 200k.
#
# Read this from the *model attachment* record, never from `message.model`: that field carries the id with
# the suffix stripped (`claude-opus-5`, for a session that is actually `claude-opus-5[1m]`), so a reading
# taken from it silently understates a 1M window by a factor of five. The attachment also carries a
# `marketingName` — "Opus 5 (1M context)" — which is what the `[1m]` mapping below is checked against.
LONG_CONTEXT_SUFFIX = "[1m]"
LONG_CONTEXT_WINDOW = 1_000_000
DEFAULT_WINDOW = 200_000

def parse_window(text: str) -> int:
    """Parse a window size: a plain count, or one with a `k` or `m` suffix (`200k`, `1m`)."""
    text = text.strip().lower().replace(",", "").replace("_", "")
    multiplier = {"k": 1000, "m": 1000000}.get(text[-1:], 1)
    if multiplier != 1:
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a window size: {text!r} (try 1m, 200k, or a plain number)") from None

def project_dir_for(path: pathlib.Path) -> pathlib.Path:
    """The log directory Claude Code uses for a working directory.

    The encoding is the absolute path with every `/` replaced by `-`, so `/home/jje/Documents/koodit/raven`
    becomes `-home-jje-Documents-koodit-raven`.
    """
    return PROJECTS / str(path.resolve()).replace("/", "-")

def resolve_log(argument: str | None) -> pathlib.Path:
    """Find the session log to read.

    `argument`: a path to a `.jsonl`, a bare session UUID, or `None` for the newest session of the current
                working directory's project.

    The default is per *project* rather than newest-overall on purpose: concurrent sessions on different
    projects are normal here, and picking the newest of all of them would silently answer about the wrong
    one — a wrong number that looks entirely right.
    """
    if argument:
        candidate = pathlib.Path(argument)
        if candidate.is_file():
            return candidate
        matches = sorted(PROJECTS.glob(f"*/{argument}.jsonl"))
        if matches:
            return matches[0]
        sys.exit(f"cc-context: no session log for {argument!r}")

    directory = project_dir_for(pathlib.Path.cwd())
    if not directory.is_dir():
        sys.exit(f"cc-context: no logs for this directory (looked in {directory}).\n"
                 f"            Run it from the project you are asking about, or name a session.")
    logs = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        sys.exit(f"cc-context: {directory} holds no session logs.")
    return logs[0]

def scan(log: pathlib.Path) -> tuple[dict, str | None, str | None, str | None]:
    """Read `log` once, returning `(usage, timestamp, model_id, marketing_name)`.

    The usage is the newest one reported; the model is the newest *attachment* naming one, which is not the
    same record and can change mid-session when the model is switched.
    """
    usage = timestamp = model_id = marketing_name = None
    with log.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except ValueError:  # a partially written final line, while the session is live
                continue
            message = record.get("message") or {}
            if message.get("usage"):
                usage, timestamp = message["usage"], record.get("timestamp")
            attachment = record.get("attachment") or {}
            if attachment.get("type") == "model":
                identity = attachment.get("identity") or {}
                model_id = identity.get("modelId") or model_id
                marketing_name = identity.get("marketingName") or marketing_name
    if usage is None:
        sys.exit(f"cc-context: {log.name} reports no usage yet.")
    return usage, timestamp, model_id, marketing_name

def window_for(model_id: str | None) -> tuple[int, bool]:
    """Return `(window, derived)` for a model id — `derived` says whether the id actually decided it."""
    if not model_id:
        return DEFAULT_WINDOW, False
    if model_id.strip().lower().endswith(LONG_CONTEXT_SUFFIX):
        return LONG_CONTEXT_WINDOW, True
    return DEFAULT_WINDOW, True

def describe_age(timestamp: str | None) -> str:
    """How long ago the reading was taken, as a phrase, or an empty string if it cannot be told."""
    if not timestamp:
        return ""
    try:
        taken = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return ""
    seconds = (datetime.datetime.now(datetime.timezone.utc) - taken).total_seconds()
    if seconds < 90:
        return f", {seconds:.0f}s ago"
    if seconds < 5400:
        return f", {seconds / 60:.0f} min ago"
    return f", {seconds / 3600:.1f} h ago"

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session", nargs="?", default=None,
                        help="path to a session .jsonl, or a session UUID. Default: the newest session of "
                             "the current directory's project.")
    parser.add_argument("-w", "--window", type=parse_window, default=None,
                        help="override the context window size (e.g. 1m, 200k). Normally unnecessary: it is "
                             "read from the model the session logged.")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="print only the token count, for use in a script.")
    args = parser.parse_args()

    log = resolve_log(args.session)
    usage, timestamp, model_id, marketing_name = scan(log)
    fill = sum(usage.get(field, 0) for field in PROMPT_FIELDS)

    if args.quiet:
        print(fill)
        return

    derived_window, derived = window_for(model_id)
    window = args.window if args.window is not None else derived_window
    window_text = f"{window / 1e6:g}M" if window >= 1e6 else f"{window / 1e3:g}k"
    # Say where the window came from, because a percentage against the wrong window is the exact failure
    # this script exists to prevent, and it looks identical to a right one.
    if args.window is not None:
        source = "as given"
    elif derived:
        source = f"from {marketing_name or model_id}"
    else:
        source = "assumed; the log named no model"

    print(f"{fill:,} tokens in the prompt  ({100.0 * fill / window:.0f}% of {window_text}, {source})")
    print(f"  session {log.stem[:8]}{describe_age(timestamp)}")

if __name__ == "__main__":
    main()
