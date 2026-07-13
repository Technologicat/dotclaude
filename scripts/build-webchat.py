#!/usr/bin/env python3
"""Expand `CLAUDE_webchat.md` into a paste-ready claude.ai userPreferences blob.

Why this exists, since it is almost never run:

The userPreferences blob lives on Anthropic's servers and is edited through the
web UI. `CLAUDE_webchat.md` is a local backup of it. In the normal course of
things you never need to rebuild the blob from the backup — you just edit it
online.

This script is a raptor contingency. If the online configuration ever becomes
inaccessible — account problem, server-side data loss, a migration that eats the
field — the blob has to be reconstructible without redoing the week of tuning
that produced its wording. That reconstruction should be one command, not a
manual splice-and-paste performed under stress.

Hence also the choice of Python over a shell one-liner: the point is
auditability. You are meant to be able to read this file, in a hurry, and be
sure of what it will do before you run it.

What it does:

  1. Reads `CLAUDE_webchat.md` (the tracked, public template).
  2. Replaces each line that is exactly `@./SECRET-SAUCE.md` with the contents of
     that file. `SECRET-SAUCE.md` is gitignored, so the template can live on a
     public GitHub repo while the assembled blob stays local. A missing
     SECRET-SAUCE.md is not an error — the placeholder line simply drops out,
     mirroring how Claude Code treats a dangling `@import` in CLAUDE.md.
  3. Strips HTML comments. The template carries a note-to-self at the top
     explaining what it is; claude.ai would read that as part of the preferences.
  4. Writes `CLAUDE_webchat.expanded.md` (gitignored) and, if `xclip` is
     available, puts the result on the clipboard ready to paste.
"""

import re
import shutil
import subprocess
import sys

from pathlib import Path

__all__ = ["expand", "strip_comments", "main"]

CLAUDE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = CLAUDE_DIR / "CLAUDE_webchat.md"
OUTPUT = CLAUDE_DIR / "CLAUDE_webchat.expanded.md"

IMPORT_LINE = "@./SECRET-SAUCE.md"


def expand(template_text, base_dir):
    """Inline `@./…` import lines in `template_text`, relative to `base_dir`.

    A line whose stripped content is exactly an import line is replaced by the
    imported file's text. A missing import target expands to nothing.
    """
    out = []
    for line in template_text.splitlines():
        if line.strip() != IMPORT_LINE:
            out.append(line)
            continue
        imported = base_dir / IMPORT_LINE.removeprefix("@./")
        if imported.exists():
            out.append(imported.read_text(encoding="utf-8").rstrip("\n"))
        else:
            print(f"note: {imported.name} not present; placeholder dropped.", file=sys.stderr)
    return "\n".join(out) + "\n"


def strip_comments(text):
    """Remove HTML comments, and any blank lines they leave behind at the top."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).lstrip("\n")


def main():
    if not TEMPLATE.exists():
        print(f"error: {TEMPLATE} not found.", file=sys.stderr)
        return 1

    expanded = strip_comments(expand(TEMPLATE.read_text(encoding="utf-8"), CLAUDE_DIR))
    OUTPUT.write_text(expanded, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(expanded)} chars).")

    if shutil.which("xclip"):
        subprocess.run(["xclip", "-selection", "clipboard"],
                       input=expanded, text=True, check=True)
        print("Copied to clipboard. Paste into claude.ai → Settings → Personal preferences.")
    else:
        print("xclip not found; paste from the file above.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
