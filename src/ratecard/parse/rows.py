"""What a parser emits. One row, with its provenance already attached.

The design rule from the architecture holds here: a price can never exist
without a source and a date. That is why `source_id` and `as_of` are on the row
itself rather than joined on later, and why `display_ok` travels with it - a
Guwahati price must be unable to reach a public view even if someone downstream
forgets which file it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RawRow:
    raw_name: str
    source_id: str
    price: str | None = None
    tier: str | None = None
    service_code: str | None = None
    service_type: str | None = None
    as_of: date | None = None
    display_ok: bool = False
    page: int | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "raw_name": self.raw_name,
            "source": self.source_id,
            "price": self.price or "",
            "tier": self.tier or "",
            "service_code": self.service_code or "",
            "service_type": self.service_type or "",
            "as_of": self.as_of.isoformat() if self.as_of else "",
            "display_ok": str(self.display_ok),
        }


FIELDS = ["raw_name", "source", "price", "tier", "service_code",
          "service_type", "as_of", "display_ok"]


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Rows, plus an honest account of what did not become one.

    `unparsed` and `skipped` are deliberately separate. A PDF row carrying a
    service code that the pattern could not read is a failure and should be
    visible - that bug once cost 16% of a source. A sitemap URL pointing at a
    package or a city page is not a failure; it is the adapter doing its job.
    Reporting 102,067 "unparsed" for the second kind buries the first.
    """

    rows: list[RawRow]
    unparsed: int = 0
    skipped: int = 0

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)
