"""Features for one (raw name, candidate) pair.

The model learns a single decision: is this candidate the right answer for this
raw name? Candidate generation already finds the right answer when one exists -
the train labels show zero confusions between canonical tests. What fails is
accepting a candidate for a name that is not in the taxonomy at all, so most of
these features exist to detect that.

The feature that matters most is out-of-vocabulary content. Every overreach in
the train split carries words that appear nowhere in the taxonomy's 1,046
surface forms - "viral load", "receptor", "reverse", "immunohistochemistry",
"aspirate". A name that is mostly vocabulary the taxonomy has never used is
very unlikely to be one of its tests, however well one word scores. The
vocabulary is built from the taxonomy itself, not a hand-written list.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from rapidfuzz import fuzz

from ratecard.names import normalise
from ratecard.normalise import rules
from ratecard.normalise.attributes import extract
from ratecard.taxonomy.loader import Taxonomy

# Ordered. The model file stores this list and refuses to load against a
# different one, so a silent reorder cannot corrupt predictions.
FEATURE_NAMES: tuple[str, ...] = (
    "wratio",               # score against the candidate's best surface form
    "token_set",
    "token_sort",
    "name_wratio",          # score against the canonical name alone
    "is_top",               # 1 for the highest-ranked survivor
    "gap_to_top",           # how far behind the leader (0 for the leader)
    "gap_to_next",          # lead over the next candidate
    "raw_tokens",           # length of the raw name, in content tokens
    "uncovered_tokens",     # raw tokens absent from THIS candidate's surfaces
    "uncovered_frac",
    "oov_tokens",           # raw tokens absent from the WHOLE taxonomy
    "oov_frac",
    "specimen_agrees",      # raw names a specimen and it matches the candidate
    "declared_distinct",    # candidate and runner-up are a curated pair
    "is_panel",
)

_NOISE = frozenset({"test", "tests", "the", "of", "and", "for", "with", "in"})


def _content(tokens) -> list[str]:
    """Tokens that carry meaning: drop noise and bare numbers."""
    return [t for t in tokens if t not in _NOISE and not t.isdigit()]


@dataclass
class Featuriser:
    taxonomy: Taxonomy

    @cached_property
    def vocabulary(self) -> frozenset[str]:
        """Every word the taxonomy ever uses, across names and aliases."""
        words: set[str] = set()
        for test in self.taxonomy:
            for surface in (test.name, *test.aliases):
                words |= set(normalise(surface).split())
        return frozenset(words)

    @cached_property
    def _surface_words(self) -> dict[str, frozenset[str]]:
        out: dict[str, frozenset[str]] = {}
        for test in self.taxonomy:
            words: set[str] = set()
            for surface in (test.name, *test.aliases):
                words |= set(normalise(surface).split())
            out[test.id] = frozenset(words)
        return out

    def pair(self, raw_name: str, candidate, ranked: list) -> list[float]:
        """Feature vector for `candidate` among the ranked survivors."""
        query = normalise(raw_name)
        test = self.taxonomy[candidate.test_id]
        raw = _content(query.split())
        n = max(len(raw), 1)

        uncovered = [t for t in raw if t not in self._surface_words[test.id]]
        oov = [t for t in raw if t not in self.vocabulary]

        position = next(i for i, c in enumerate(ranked) if c.test_id == candidate.test_id)
        top = ranked[0].score
        nxt = ranked[position + 1].score if position + 1 < len(ranked) else 0.0

        raw_specimen = extract(raw_name).specimen
        specimen_agrees = float(raw_specimen is not None and raw_specimen == test.specimen)

        declared = 0.0
        if len(ranked) > 1:
            other = ranked[1] if position == 0 else ranked[0]
            declared = float(rules.blocks(test, self.taxonomy[other.test_id]))

        return [
            candidate.score / 100.0,
            fuzz.token_set_ratio(query, candidate.surface) / 100.0,
            fuzz.token_sort_ratio(query, candidate.surface) / 100.0,
            fuzz.WRatio(query, normalise(test.name)) / 100.0,
            float(position == 0),
            (top - candidate.score) / 100.0,
            (candidate.score - nxt) / 100.0,
            float(len(raw)),
            float(len(uncovered)),
            len(uncovered) / n,
            float(len(oov)),
            len(oov) / n,
            specimen_agrees,
            declared,
            float(test.is_panel),
        ]
