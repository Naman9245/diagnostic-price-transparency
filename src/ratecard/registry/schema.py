"""What the pipeline needs to know about a source before it fetches anything.

Stage 1. This replaces the module-level dicts in
`scripts/phase00_seed_corpus.py`, which were fine for a throwaway but encode
three things the real pipeline cannot hardcode.

**Tier vocabulary is per-document.** Phase 00 found the two Narayana units
using different schemas - 11 price columns in Bengaluru, 8 in Guwahati, with
different names. `price_tier` therefore cannot be a shared enum, and each
source has to carry its own column list plus which one is the walk-in rate.

**Provenance is not optional.** A price row can never exist without a source
and a date, so the registry is where `sha256`, `as_of` and `retrieved` live.
A pinned hash is what lets the fetcher refuse a silently reissued document.

**Permission is per-source and must be written down.** `licence_note` is
required, not because a schema can make a judgement, but because leaving the
field blank is a decision someone has to make deliberately rather than by
forgetting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Format(StrEnum):
    PDF = "pdf"
    HTML = "html"
    SITEMAP = "sitemap"


class Refresh(StrEnum):
    """How often the publisher is expected to reissue. Drives re-fetch, and
    Phase 07's staleness flag."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    publisher: str
    url: str
    format: Format
    parser: str

    # -- where and what ---------------------------------------------------
    city: str | None = None
    unit: str | None = None

    # -- provenance -------------------------------------------------------
    sha256: str | None = None
    as_of: date | None = None
    retrieved: date | None = None
    refresh: Refresh = Refresh.UNKNOWN

    # -- pricing ----------------------------------------------------------
    # Ordered exactly as the columns appear in the document.
    tiers: tuple[str, ...] = ()
    # Which of `tiers` is the outpatient walk-in rate - the only tier that can
    # be compared across publishers.
    comparison_tier: str | None = None

    # -- governance -------------------------------------------------------
    # False means names may be harvested but no price may ever reach a public
    # view. The Guwahati file is the reason this exists: the census reported
    # its prices as Bengaluru ones.
    display_ok: bool = False
    licence_note: str = ""
    notes: str | None = None

    @property
    def carries_prices(self) -> bool:
        return bool(self.tiers)

    @property
    def comparison_index(self) -> int | None:
        """Position of the walk-in column, for the parser to read."""
        if self.comparison_tier is None or self.comparison_tier not in self.tiers:
            return None
        return self.tiers.index(self.comparison_tier)

    def __str__(self) -> str:  # pragma: no cover - convenience only
        where = self.city or "—"
        return f"{self.id} ({self.publisher}, {where})"
