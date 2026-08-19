#!/usr/bin/env python3
"""Measure how densely a diff uses contrastive constructions, against a baseline of hand-written prose.

"X, not Y" earns its place when a reader would actually have assumed Y, and the rule saying so has been in
CLAUDE.md for a long time. It does not hold, on any model tried: the construction is produced anyway, roughly
every session. This measures the overuse instead of arguing with it.

Why a *density* and not a per-line verdict, which is what a linter would normally do:

- **Per-line is unfalsifiable.** Whether a foil is real is a claim about what a reader would have assumed.
  Nobody can check it from the line, so a `# noqa` beside one asserts exactly the thing in question.
- **The writer is the wrong judge.** Asked to rule on four of its own foils, an agent kept all four — and
  the fourth was a foil it had already made three lines earlier. Absolute judgement is where it fails.
- **Ranking is a different question, and a survivable one.** "Which five of these thirty are weakest" gets a
  usable answer where "is this one justified" does not. Cutting to a budget only ever asks the first.
- **A density cannot be laundered one line at a time**, so there is nothing to suppress and no second-order
  problem of a suppression comment becoming reflexive.

The baseline is Juha's own long-standing prose, measured 2026-08-19 over seven corpora and some 590k words
of `.py` / `.pyx` / `.pxd` / `.md` (`--baseline` re-measures any of it):

    pylu             0.00 per 1000 words     hand-written, Cython numerics
    wlsqm            0.02
    pydgq            0.03
    extrafeathers    0.03                    hand-written, FEM
    randomthought    0.06                    hand-written, ML
    unpythonic       0.08                    hand-written, language tooling
    mcpyrate         0.11

    raven/common/gui        1.50             agent era
    raven .../fdialog.py    3.78             agent era, mostly one day

Seven corpora spanning numerics, FEM, ML and macro tooling land between 0.00 and 0.11; agent-written code
sits fourteen to seventy-five times higher. Hence a target of 0.5 — an order of magnitude above the worst
hand-written number, so an earned one costs nothing and the habit still shows. Over it, cut the weakest
until it fits. Under it there is nothing to do; a low density is no licence to add one.

Advisory by default: it exits 0 whatever it finds, because the count is an instrument and the judgement
stays with the person reading. `--strict` exits 1 when over budget, for wiring into a hook.

Usage:
    check-prose.py                       # staged changes (what a commit is about to record)
    check-prose.py --unstaged            # working tree against the index
    check-prose.py --range HEAD~3        # everything added since that commit
    check-prose.py --list                # ...and print the individual hits, to spot-check them
    check-prose.py --baseline DIR [DIR]  # re-measure whole trees, to re-derive the target
    check-prose.py FILE [FILE ...]       # whole files, ignoring git

Deploy by symlinking onto PATH, so this stays the single copy:

    ln -s ~/.claude/scripts/check-prose.py ~/.local/bin/check-prose
"""

import argparse
import pathlib
import re
import subprocess
import sys
from typing import Iterable, Iterator, Optional

# Which files hold prose worth measuring. Source files count: the tics live in comments and docstrings.
PROSE_SUFFIXES = {".py", ".pyx", ".pxd", ".md", ".rst", ".txt", ".toml", ".yaml", ".yml", ".sh"}

# Narrowed to what the measurement actually indicts. Broken down by marker across the same corpora
# (2026-08-19, per 1000 words):
#
#     marker          mcpyrate  unpythonic   raven/common/gui   fdialog.py
#     rather than         0.04        0.03               2.05         3.78
#     instead of          0.24        0.54               0.31         0.52
#     "not X, it's Y"     0.07        0.05               0.00         0.06
#
# So `instead of` is ordinary English, used at the same rate by everyone, and the "not X, it's Y" shape is
# not this model's habit at all — Juha's read was that it belongs to GPT and Qwen, and the numbers agree.
# Nearly the whole anomaly is one phrase, at sixty to a hundred times the hand-written rate. Measuring the
# others dilutes it.
CONTRASTIVE = re.compile(r"\brather than\b|\bnot merely\b", re.IGNORECASE)

# The hand-written corpora sit at 0.03–0.04. Set an order of magnitude above the worst of them, so that the
# check fires on the habit and stays quiet about the occasional earned one.
TARGET_PER_1000 = 0.5

# Enough words for a rate to mean anything. Below this, the raw count is reported and no verdict is given —
# three contrastives in forty words is not a density, it is three contrastives.
MIN_WORDS_FOR_A_RATE = 200

# Tics that are absolute rather than statistical: one is one too many, so they are listed, not counted
# against a budget.
ABSOLUTES = [
    ("register named",
     re.compile(r"\b(?:deadpan|tongue-in-cheek|Easter egg|playful)\b", re.IGNORECASE),
     "naming the tone in the artifact is the wink; delete the clause"),
    ("hedge in a durable artifact",
     re.compile(r"\b(?:presumably|probably|it seems|apparently|arguably)\b", re.IGNORECASE),
     "check it or cut it; a hedged guess still has to be re-litigated by whoever reads it next"),
]


def added_lines_from_diff(diff: str) -> Iterator[tuple[str, int, str]]:
    """Yield `(path, line number, text)` for every line a unified diff adds to a prose file."""
    path: Optional[str] = None
    lineno = 0
    interesting = False
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            interesting = pathlib.Path(path).suffix in PROSE_SUFFIXES
        elif line.startswith("@@"):
            # "@@ -a,b +c,d @@" — `c` is where the added side resumes.
            match = re.search(r"\+(\d+)", line)
            lineno = int(match.group(1)) if match else 0
        elif interesting and line.startswith("+") and not line.startswith("+++"):
            yield path, lineno, line[1:]
            lineno += 1
        elif not line.startswith("-"):
            lineno += 1


def lines_from_files(paths: Iterable[str]) -> Iterator[tuple[str, int, str]]:
    """Yield `(path, line number, text)` for every line of the named files."""
    for path in paths:
        if pathlib.Path(path).suffix not in PROSE_SUFFIXES:
            continue
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            yield path, lineno, line


def lines_under(directories: Iterable[str]) -> Iterator[tuple[str, int, str]]:
    """Yield every prose line under the given directories, for `--baseline`."""
    for directory in directories:
        for path in sorted(pathlib.Path(directory).rglob("*")):
            if path.is_file() and path.suffix in PROSE_SUFFIXES:
                yield from lines_from_files([str(path)])


def measure(lines: Iterable[tuple[str, int, str]]) -> tuple[int, int, list[tuple[str, int, str, str]]]:
    """Count words and contrastives. Returns `(words, hits, [(path, lineno, text, matched)])`."""
    words = 0
    found = []
    for path, lineno, text in lines:
        words += len(text.split())
        for match in CONTRASTIVE.finditer(text):
            found.append((path, lineno, text, match.group(0)))
    return words, len(found), found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="check these files entire, ignoring git")
    parser.add_argument("--unstaged", action="store_true", help="check the working tree against the index")
    parser.add_argument("--range", metavar="COMMIT", help="check everything added since COMMIT")
    parser.add_argument("--baseline", nargs="+", metavar="DIR", help="measure whole trees, to re-derive the target")
    parser.add_argument("--list", action="store_true", help="print the individual hits as well as the rate")
    parser.add_argument("--strict", action="store_true", help="exit 1 when over budget")
    args = parser.parse_args()

    if args.baseline:
        for directory in args.baseline:
            words, hits, _found = measure(lines_under([directory]))
            rate = hits / max(words, 1) * 1000
            print(f"{directory}: {hits} / {words} words = {rate:.2f} per 1000")
        return 0

    if args.files:
        lines = lines_from_files(args.files)
    else:
        command = ["git", "diff", "--unified=0"]
        if args.range:
            command.append(args.range)
        elif not args.unstaged:
            command.append("--cached")
        diff = subprocess.run(command, capture_output=True, text=True, check=True).stdout
        lines = added_lines_from_diff(diff)

    lines = list(lines)  # scanned twice: once for the rate, once for the tics that are not statistical
    words, hits, found = measure(lines)

    if args.list:
        for path, lineno, text, matched in found:
            print(f"{path}:{lineno}: '{matched}'")
            print(f"    {text.strip()}")
        if found:
            print()

    for name, pattern, advice in ABSOLUTES:
        for path, lineno, text in lines:
            match = pattern.search(text)
            if match is not None:
                print(f"{path}:{lineno}: {name}: '{match.group(0)}'")
                print(f"    {text.strip()}")
                print(f"    -> {advice}")

    if words < MIN_WORDS_FOR_A_RATE:
        print(f"{hits} contrastive(s) in {words} added words — too little prose for a rate.")
        return 0

    rate = hits / words * 1000
    verdict = "over" if rate > TARGET_PER_1000 else "within"
    print(f"{hits} contrastive(s) / {words} added words = {rate:.2f} per 1000 ({verdict} the {TARGET_PER_1000} target).")
    if rate > TARGET_PER_1000:
        excess = hits - int(TARGET_PER_1000 * words / 1000)
        print(f"Cut the {excess} weakest to fit. Rank them against each other; do not defend them one at a time.")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
