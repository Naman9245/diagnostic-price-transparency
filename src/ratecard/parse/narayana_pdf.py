"""Parse a Narayana Health schedule of charges.

Generalised from the Phase 00 script, which hardcoded 11 columns for Bengaluru
and 8 for Guwahati. The column count now comes from `len(source.tiers)` and the
price is read at `source.comparison_index`, so a third unit with yet another
schema is a registry entry rather than another branch here.

Two shapes of damage in the extracted text, both found the hard way:

  - long names wrap, pushing the price run onto the following line. Requiring a
    full price run on one line silently dropped 291 of Guwahati's 1,792 rows.
  - the service type leads on most pages and trails the prices on some.
"""

from __future__ import annotations

import re

from ratecard.parse.rows import ParseResult, RawRow
from ratecard.registry import Source

MONEY = r"(?:[\d,]+|-)"
RE_RECORD_START = re.compile(r"^(?:[A-Za-z][A-Za-z /&-]*?\s+)?SVC\d+", re.MULTILINE)


def _row_pattern(tier_count: int) -> re.Pattern[str]:
    """A row is an optional service type, a code, a name, then N prices, then
    optionally the service type again."""
    return re.compile(
        rf"^(?:([A-Za-z][A-Za-z /&-]*?)\s+)?(SVC\d+)\s+(.+?)\s+"
        rf"({MONEY}(?:\s+{MONEY}){{{tier_count - 1}}})"
        rf"(?:\s+[A-Za-z][A-Za-z /&-]*)?\s*$",
        re.MULTILINE,
    )


def join_wrapped_rows(text: str, row_pattern: re.Pattern[str]) -> str:
    """Rejoin rows the PDF text layer split across lines."""
    out: list[str] = []
    buffer = ""
    for line in text.splitlines():
        starts = RE_RECORD_START.match(line) is not None
        if buffer and (starts or row_pattern.match(buffer)):
            out.append(buffer)
            buffer = line if starts else ""
            continue
        if starts:
            buffer = line
        elif buffer:
            buffer = f"{buffer} {line.strip()}"
            if row_pattern.match(buffer):
                out.append(buffer)
                buffer = ""
        else:
            out.append(line)
    if buffer:
        out.append(buffer)
    return "\n".join(out)


def _price(cell: str) -> str | None:
    cell = cell.strip().replace(",", "")
    return None if cell in {"-", ""} else cell


def parse(text: str, source: Source) -> ParseResult:
    """Return rows plus the count of service-code lines that would not parse.

    The second element is not decoration. A parser that loses 16% of a source
    without saying so is worse than one that fails loudly, and that is exactly
    what this one used to do.
    """
    tier_count = len(source.tiers)
    if tier_count < 2:
        raise ValueError(f"{source.id}: needs at least two price tiers to parse")

    pattern = _row_pattern(tier_count)
    text = join_wrapped_rows(text, pattern)
    expected = sum(1 for line in text.splitlines() if re.search(r"SVC\d", line))
    index = source.comparison_index or 0

    rows: list[RawRow] = []
    for match in pattern.finditer(text):
        service_type, code, name, prices = match.groups()
        name = re.sub(r"\s+", " ", name).strip()
        if not name or name.lower().startswith("service name"):
            continue
        cells = prices.split()
        rows.append(RawRow(
            raw_name=name,
            source_id=source.id,
            price=_price(cells[index]) if index < len(cells) else None,
            tier=source.comparison_tier,
            service_code=code,
            service_type=(service_type or "").strip() or None,
            as_of=source.as_of,
            display_ok=source.display_ok,
        ))
    return ParseResult(rows, unparsed=max(0, expected - len(rows)))
