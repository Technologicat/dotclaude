"""Whether `check_changelog_format.py` would notice a changelog that is actually wrapped.

**Every case here feeds the checker a document broken on purpose**, following `check_doc_links.py`'s
tests, which are this file's model. A checker that has only ever seen a correct changelog cannot show
that it would report an incorrect one — and this one shipped a first draft that reported three *correct*
paragraphs in Raven's `0.1.x and older` section as wraps, which no amount of running it against the
already-fixed release section would have revealed.

The four false-positive classes each have a case, because each was found by running the draft against
real files rather than by reading it: fenced code, tables, horizontal rules, and a paragraph that merely
follows a blank line.

    python -m pytest ~/.claude/skills/changelog/tests/ -q
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from check_changelog_format import entries, sections, wrapped_lines  # noqa: E402 -- needs the path entry


# The baseline every other case perturbs: a titled entry whose prose sits under it, which is the shape
# the house format asks for. If this one ever reports a wrap, the perturbed cases prove nothing.
GOOD = """\
## 0.3.0 (in progress)

### Added

#### Raven-librarian

- **A titled entry.**
  Its prose sits on the next line, which is prose under a lead and not a wrap.
  - **A nested bullet**, carrying the rest of its own sentence on the same line.
  - Another nested bullet, one line long however far it runs and no matter how much it has to say.
""".splitlines()


def test_the_house_format_reports_nothing():
    assert wrapped_lines(GOOD) == []


def test_a_wrapped_bullet_is_reported():
    lines = GOOD + ["- **An entry whose sentence runs past the end of its line and",
                    "  continues here**, which is the thing this checker is for."]
    assert wrapped_lines(lines) == [len(lines)]


def test_a_wrapped_continuation_of_prose_is_reported():
    lines = GOOD + ["- **A title.**", "  Prose that stops mid-sentence and",
                    "  carries on down here."]
    assert wrapped_lines(lines) == [len(lines)]


class TestWhatIsNotProse:
    """The four false-positive classes, each found by running the draft against a real changelog."""

    def test_fenced_code_is_not_wrapped_prose(self):
        lines = GOOD + ["- **An entry with a command in it.**", "",
                        "  ```", "  raven-deduplicate search.bib -o deduped.bib", "  ```"]
        assert wrapped_lines(lines) == []

    def test_a_table_is_not_wrapped_prose(self):
        lines = GOOD + ["- **An entry with a table.**", "",
                        "  | key | what it does |", "  |---|---|", "  | `F1` | opens the card |"]
        assert wrapped_lines(lines) == []

    def test_a_horizontal_rule_is_not_wrapped_prose(self):
        for rule in ("---", "***", "- - -"):
            assert wrapped_lines(GOOD + ["", rule]) == [], rule

    def test_a_paragraph_after_a_blank_line_is_not_a_continuation(self):
        # The case the draft got wrong: with a blank line above, there is nothing for this to have
        # wrapped *from*, however it ends.
        lines = GOOD + ["", "The project was started in December 2024", "",
                        "No changelog was maintained"]
        assert wrapped_lines(lines) == []


class TestSections:
    def test_each_release_heading_starts_a_section(self):
        lines = GOOD + ["## 0.2.9 (1 January 2026)", "", "- **An older entry.**"]
        found = sections(lines)
        assert [title for title, _, _ in found] == ["## 0.3.0 (in progress)", "## 0.2.9 (1 January 2026)"]

    def test_a_wrap_is_attributed_to_the_section_holding_it(self):
        lines = GOOD + ["## 0.2.9 (1 January 2026)", "",
                        "- **An entry that stops mid-sentence and", "  wraps.**"]
        _, start, end = sections(lines)[1]
        assert wrapped_lines(lines, start, end) == [len(lines)]
        # ...and the first section is still clean, so the range is doing the work rather than luck.
        _, start, end = sections(lines)[0]
        assert wrapped_lines(lines, start, end) == []


class TestEntries:
    def test_entries_are_counted_with_their_children(self):
        found = entries(GOOD, 0, len(GOOD))
        assert len(found) == 1, "the nested bullets belong to the entry above them, not to themselves"
        line_no, words, text = found[0]
        assert text.startswith("**A titled entry.")
        assert words > 25, "the entry's own children count toward its length; that is the point of the report"


if __name__ == "__main__":
    pytest.main([__file__])
