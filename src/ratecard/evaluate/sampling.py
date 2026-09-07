"""Draw the labelling set.

Deliberately **stratified, not uniform**, and that has a consequence the
write-up has to be honest about: the raw rates measured on this sample are not
corpus rates. A uniform draw from 11,682 names would be dominated by surgical
procedures and specialist assays where the right answer is "none", and 350
labels teaching us that the matcher correctly declines to match ABOVE ELBOW
AMPUTATION is 350 labels wasted.

So each stratum is sampled to a quota chosen for what it can teach, and every
row records which stratum it came from. `metrics.evaluate` reports per-stratum
figures and, where a corpus-level estimate is wanted, reweights by the true
stratum sizes rather than pretending the sample was uniform.

The hard slice is the interesting one. It is drawn from names where the matcher
was nearly wrong rather than plainly wrong: thin-margin abstentions, and names
whose top two candidates are a pair a curator explicitly declared distinct.
Those are the pairs the whole veto layer exists for, and the number that will
matter in the write-up is accuracy on them specifically.
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ratecard.normalise import rules
from ratecard.normalise.matcher import Match, Matcher
from ratecard.taxonomy.loader import Taxonomy

# stratum -> how many to draw, and why that many.
STRATA: dict[str, tuple[int, str]] = {
    "exact": (60, "alias hits - are the aliases themselves right?"),
    "lexical": (140, "the risk surface: confident answers that may be wrong"),
    "abstain_thin_margin": (100, "near-misses; the veto layer's home ground"),
    "abstain_low_score": (60, "did we refuse something we should have taken?"),
    "abstain_no_candidate": (60, "mostly true negatives; confirms the floor"),
    "abstain_vetoed": (40, "did a hard rule over-fire?"),
    "declared_distinct_neighbour": (40, "top two are a curated hard-negative pair"),
}

HOLDOUT_FRACTION = 0.30

FIELDS = [
    "raw_name", "stratum", "split", "row_count", "sources",
    "matcher_guess", "matcher_method", "matcher_confidence",
    "candidates", "label", "labelled_by", "note",
]


@dataclass(frozen=True, slots=True)
class SampleRow:
    raw_name: str
    stratum: str
    split: str
    row_count: int
    sources: str
    match: Match

    def candidate_ids(self, limit: int = 8) -> list[str]:
        """Plausible answers, **without** revealing which one the matcher chose.

        Anchoring is a real risk when a human labels 500 rows against a
        machine's suggestion. Showing the candidate pool is unavoidable - 210
        options is more than anyone can hold in their head - but showing which
        one won, and with what score, is not. They are sorted by id here rather
        than by score for the same reason.
        """
        seen: list[str] = []
        for candidate in self.match.candidates:
            if not candidate.blocked and candidate.test_id not in seen:
                seen.append(candidate.test_id)
        return sorted(seen[:limit])


def _stratum_of(match: Match, taxonomy: Taxonomy) -> str:
    if match.method == "abstain_thin_margin" and len(match.candidates) >= 2:
        survivors = [c for c in match.candidates if not c.blocked][:2]
        if len(survivors) == 2 and rules.blocks(taxonomy[survivors[0].test_id],
                                                taxonomy[survivors[1].test_id]):
            return "declared_distinct_neighbour"
    return match.method


def build_sample(
    taxonomy: Taxonomy,
    corpus_path: Path,
    seed: int = 20260905,
    strata: dict[str, tuple[int, str]] | None = None,
) -> tuple[list[SampleRow], Counter[str]]:
    """Match the whole corpus, bucket by stratum, then draw each quota."""
    quotas = strata or STRATA
    rng = random.Random(seed)

    counts: Counter[str] = Counter()
    sources: dict[str, set[str]] = {}
    with corpus_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("raw_name") or "").strip()
            if not name:
                continue
            counts[name] += 1
            sources.setdefault(name, set()).add(row.get("source", "unknown"))

    matcher = Matcher(taxonomy)
    buckets: dict[str, list[tuple[str, Match]]] = {}
    for name in sorted(counts):
        match = matcher.match(name)
        buckets.setdefault(_stratum_of(match, taxonomy), []).append((name, match))

    population = Counter({stratum: len(rows) for stratum, rows in buckets.items()})

    drawn: list[SampleRow] = []
    for stratum, (quota, _why) in quotas.items():
        available = buckets.get(stratum, [])
        picked = rng.sample(available, min(quota, len(available)))
        for name, match in picked:
            drawn.append(SampleRow(
                raw_name=name,
                stratum=stratum,
                split="holdout" if rng.random() < HOLDOUT_FRACTION else "train",
                row_count=counts[name],
                sources="|".join(sorted(sources.get(name, ()))),
                match=match,
            ))

    rng.shuffle(drawn)
    return drawn, population


def write_sample(rows: list[SampleRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "raw_name": row.raw_name,
                "stratum": row.stratum,
                "split": row.split,
                "row_count": row.row_count,
                "sources": row.sources,
                "matcher_guess": row.match.test_id or "",
                "matcher_method": row.match.method,
                "matcher_confidence": f"{row.match.confidence:.1f}",
                "candidates": "|".join(row.candidate_ids()),
                "label": "",        # <- the human fills this in
                "labelled_by": "",
                "note": "",
            })
