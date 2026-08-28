# Authors

*By fleet policy, both human and AI authors are listed.*

Juha Jeronen (@Technologicat):

- Author and maintainer: the working practices this repo encodes, and the rules in
  `CLAUDE.md` — decisions about how the collaboration should go, arrived at by doing it
  and noticing what went wrong.
- Direction, and review of every AI-authored changeset.
- Copyright holder for the documentation and the code.

Claude (Anthropic), as AI pair programmer — Opus 4.6, 4.8 and 5, per the commit trailers:

- Drafting and revision of the prose, worked in both directions: the rules are Juha's,
  the wording is usually joint.
- Implementation of the scripts and the test suite.
- The artwork in `icons/`, drawn by Opus 5.

Attribution per change is in the `Co-Authored-By` trailers, which name the model version.
The `commit-msg` hook in `githooks/` is what keeps that record complete.

### Why the icons have no copyright holder

There was not enough human creative direction behind them to support a claim, so none is
made; `icons/LICENSE.md` records the dedication and the reasoning. Credit and copyright
answer different questions, and only the first has an answer here — the drawing is
attributed above, and the rights line is empty on purpose.
