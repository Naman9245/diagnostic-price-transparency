"""Measure the taxonomy against a corpus of raw source names.

The Phase 01 exit criterion is "taxonomy covering 80%+ of the corpus by row
volume". This module reports that honestly, which means reporting two numbers
and not conflating them:

    exact       rows resolved by alias lookup alone. A true floor - every one
                of these is correct by construction and needs no review.
    reachable   rows whose full normalised token set is a superset of some
                canonical name's tokens. A loose ceiling estimate for what the
                Phase 02 matcher could plausibly reach. NOT a claim of
                correctness: it is a containment heuristic and it over-counts.

The real coverage number sits between the two and cannot be known until the
matcher and the labelled set exist. Quoting `reachable` as the exit number
would be dishonest, so the CLI prints both and passes on `exact`.

The genuinely useful output is `unmatched`: the highest-frequency raw names the
taxonomy does not cover, ranked. That is the curation worklist.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ratecard.names import normalise, tokens
from ratecard.taxonomy.loader import Taxonomy

# Columns the Phase 00 corpus dump is expected to carry.
NAME_COLUMNS = ("raw_name", "name", "test_name", "raw_test_name")


@dataclass
class CoverageReport:
    rows: int = 0
    distinct_names: int = 0
    exact_rows: int = 0
    exact_names: int = 0
    reachable_rows: int = 0
    reachable_names: int = 0
    unmatched: list[tuple[str, int]] = field(default_factory=list)
    per_source: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def exact_pct(self) -> float:
        return 100.0 * self.exact_rows / self.rows if self.rows else 0.0

    @property
    def reachable_pct(self) -> float:
        return 100.0 * self.reachable_rows / self.rows if self.rows else 0.0


def _name_column(fieldnames: list[str] | None) -> str | None:
    for candidate in NAME_COLUMNS:
        if fieldnames and candidate in fieldnames:
            return candidate
    return None


def _build_token_sets(taxonomy: Taxonomy) -> list[tuple[frozenset[str], str]]:
    """Token sets for every canonical surface form.

    Unordered, deliberately. An earlier version sorted these longest-first and
    claimed that let the more specific study win, but the only caller asks
    `any(...)`, which is order-independent - the sort decided nothing and the
    docstring described behaviour that was not there. `reachable` is a yes/no
    containment ceiling and does not pick between tests; that is the matcher's
    job, not this one's.
    """
    surfaces: list[tuple[frozenset[str], str]] = []
    for test in taxonomy:
        for surface in (test.name, *test.aliases):
            token_set = tokens(surface)
            if token_set:
                surfaces.append((token_set, test.id))
    return surfaces


def analyse(taxonomy: Taxonomy, corpus_path: Path, top_unmatched: int = 40) -> CoverageReport:
    """Read a Phase 00 corpus CSV and report coverage."""
    report = CoverageReport()
    surfaces = _build_token_sets(taxonomy)

    counts: Counter[str] = Counter()
    sources: dict[str, list[str]] = {}

    with corpus_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        column = _name_column(reader.fieldnames)
        if column is None:
            raise ValueError(
                f"{corpus_path} has no recognised name column "
                f"(looked for {', '.join(NAME_COLUMNS)}; found {reader.fieldnames})"
            )
        for row in reader:
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            counts[raw] += 1
            report.rows += 1
            sources.setdefault(row.get("source", "unknown"), []).append(raw)

    report.distinct_names = len(counts)

    unmatched: list[tuple[str, int]] = []
    for raw, count in counts.items():
        if taxonomy.lookup(raw) is not None:
            report.exact_rows += count
            report.exact_names += 1
            report.reachable_rows += count
            report.reachable_names += 1
            continue

        raw_tokens = tokens(raw)
        if raw_tokens and any(surface <= raw_tokens for surface, _ in surfaces):
            report.reachable_rows += count
            report.reachable_names += 1
        else:
            unmatched.append((raw, count))

    unmatched.sort(key=lambda pair: (-pair[1], pair[0]))
    report.unmatched = unmatched[:top_unmatched]

    for source, names in sources.items():
        hits = sum(1 for name in names if taxonomy.lookup(name) is not None)
        report.per_source[source] = (hits, len(names))

    return report


def hard_negative_pairs(taxonomy: Taxonomy) -> list[tuple[str, str, str]]:
    """Seed pairs for the Phase 03 hard-negative evaluation set.

    Every curated `distinct_from` declaration is, by definition, a pair a human
    thought was confusable enough to be worth writing down. That is exactly the
    selection criterion for the hard slice of the labelled set, so the eval set
    does not have to be assembled from scratch later.
    """
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str, str]] = []
    for test in taxonomy:
        for other_id in test.distinct_from:
            key = tuple(sorted((test.id, other_id)))
            if key in seen:
                continue
            seen.add(key)
            other = taxonomy.get(other_id)
            if other is None:
                continue
            shared = tokens(test.name) & tokens(other.name)
            reason = f"shares {sorted(shared)}" if shared else "no shared tokens"
            out.append((test.id, other_id, reason))
    return sorted(out)


def normalise_preview(names: list[str]) -> list[tuple[str, str]]:
    """Raw -> normalised, for eyeballing what the normaliser is doing."""
    return [(name, normalise(name)) for name in names]
