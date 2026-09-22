#!/usr/bin/env python3
"""Whether a CHANGELOG.md still follows the house format: one line per bullet.

The rule is in `SKILL.md` under "Line breaks" — a bullet runs on one line however long it gets, and a
bullet that needs more structure gets nested children rather than a wrapped second line. It lives here
rather than in any project's `scripts/` because the rule is fleet-wide, and because a rule and the thing
that enforces it are one unit: if this skill moves, its checker moves with it. Same argument as Raven's
own `.claude/skills/dpg/check_router.py`, which sits beside the skill it checks rather than in that
project's `scripts/`.

**A wrap is invisible.** Markdown folds a wrapped line and its parent back into one paragraph, so the
rendered page is identical either way and nothing — not a linter, not a test, not a reader — reports it.
That is what makes it rot: measured on Raven 2026-09-22, 100 wrapped lines had accumulated across a
release section, 56 of them left in one block by a reflow reported as finished when it was half done.

    check_changelog_format.py CHANGELOG.md            # every release section
    check_changelog_format.py CHANGELOG.md --latest   # only the topmost one, which is the one being written
    check_changelog_format.py CHANGELOG.md --report   # no pass/fail; the shape of each section

Exit 0 when clean, 1 when something is wrapped, 2 when a file cannot be read — the convention the fleet's
other checkers use, so this one can gate a commit too. It imports nothing outside the standard library,
so it runs anywhere a changelog does.
"""

import argparse
import pathlib
import re
import sys

__all__ = ["wrapped_lines", "sections", "entries", "main"]

# A line that ends a sentence, and so can legitimately be followed by prose on the next line — the
# "bold lead, then its prose indented under it" shape the skill describes for a titled entry.
SENTENCE_END = (".", ":", "?", "!", '."', ".*", ".**", ".)", '.”')

BULLET = re.compile(r"^\s*[-*+] ")
RULE = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")   # --- *** ___ , with or without spaces
HEADING = re.compile(r"^#{1,6} ")
RELEASE = re.compile(r"^## ")


def _content_lines(lines):
    """Yield `(index, line)` for lines that are prose, skipping what is not.

    Fenced code, tables and horizontal rules are the three that produced false positives when this was a
    throwaway probe: none of them is prose, and each ends a line somewhere other than a full stop.
    """
    fenced = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or RULE.match(line) or line.lstrip().startswith("|"):
            continue
        yield i, line


def sections(lines):
    """Every release section, as `(title, start, end)` with `end` exclusive."""
    starts = [i for i, line in enumerate(lines) if RELEASE.match(line)]
    return [(lines[s].strip(), s, starts[k + 1] if k + 1 < len(starts) else len(lines))
            for k, s in enumerate(starts)]


def wrapped_lines(lines, start=0, end=None):
    """Line numbers (1-based) of continuation lines that wrap rather than carry a title's prose.

    A continuation line is one that is neither blank, a bullet, nor a heading. It is *prose under a lead*
    when the line above it finished a sentence, and a *wrap* when the line above stopped mid-sentence —
    which is the distinction the format rests on, and the one a whitespace-collapsing check cannot make.
    """
    end = len(lines) if end is None else end
    found = []
    for i, line in _content_lines(lines):
        if not (start <= i < end):
            continue
        if not line.strip() or BULLET.match(line) or HEADING.match(line):
            continue
        previous = lines[i - 1].rstrip() if i else ""
        # A blank line above makes this the start of a paragraph rather than the continuation of
        # anything, so there is nothing for it to have wrapped from. Without this the checker reports
        # every standalone paragraph in a changelog's prose -- three of them in Raven's `0.1.x and
        # older` section, which is how the case was found.
        if not previous:
            continue
        if not previous.endswith(SENTENCE_END):
            found.append(i + 1)
    return found


def entries(lines, start, end):
    """Top-level entries in a section, as `(line number, word count, first line)`."""
    out, current = [], None

    def close():
        if current is not None:
            text = re.sub(r"[*`\[\]()#>-]", " ", "\n".join(current[1]))
            out.append((current[0], len(text.split()), current[2]))

    for i, line in _content_lines(lines):
        if not (start <= i < end):
            continue
        if HEADING.match(line):
            close()
            current = None
        elif re.match(r"^[-*+] ", line):
            close()
            current = (i + 1, [line], line[2:].strip()[:70])
        elif current is not None:
            current[1].append(line)
    close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="+", type=pathlib.Path, help="CHANGELOG.md file(s) to check")
    parser.add_argument("--latest", action="store_true",
                        help="check only the topmost release section, the one still being written")
    parser.add_argument("--report", action="store_true",
                        help="describe each section instead of checking it; prints the longest entries, "
                             "which is where documentation hides")
    args = parser.parse_args()

    status = 0
    for path in args.paths:
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except OSError as exc:
            print(f"FAIL: {path}: {exc}", file=sys.stderr)
            status = max(status, 2)
            continue

        found = sections(lines) or [("(whole file)", 0, len(lines))]
        if args.latest:
            found = found[:1]

        if args.report:
            for title, start, end in found:
                items = entries(lines, start, end)
                total = sum(words for _, words, _ in items)
                print(f"\n{title}\n  {len(items)} entries, {total} words")
                for line_no, words, text in sorted(items, key=lambda e: -e[1])[:5]:
                    print(f"    {words:5d}w  L{line_no:<5d} {text}")
            continue

        bad = {title: wrapped_lines(lines, start, end) for title, start, end in found}
        n = sum(len(v) for v in bad.values())
        if not n:
            print(f"OK: {path} has no wrapped lines in {len(found)} release "
                  f"section{'s' if len(found) != 1 else ''}.")
            continue
        status = max(status, 1)
        print(f"{path}: {n} wrapped line{'s' if n != 1 else ''} — a bullet runs on one line, "
              f"however long; use nested bullets for structure.", file=sys.stderr)
        for title, numbers in bad.items():
            if numbers:
                print(f"  {title}", file=sys.stderr)
                for number in numbers:
                    print(f"    line {number}: {lines[number - 1].strip()[:88]}", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
