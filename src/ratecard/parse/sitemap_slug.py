"""Harvest test names from a sitemap without fetching a single test page.

Both lab chains encode the test name in the URL slug, so the sitemap alone
carries every name - roughly 20 requests instead of 7,000, and it stays plainly
inside what robots.txt allows.

Names only. No price is harvested, so none can leak into a public comparison.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from ratecard.parse.rows import ParseResult, RawRow
from ratecard.registry import Source

LOC = re.compile(r"<loc>([^<]+)</loc>")
# Path segments that name a test rather than a page: /pathology-test/{slug},
# /radiology-tests/{slug}, /{city}/tests/{slug}, or a bare /{slug}.
#
# Matched against the *path only*, with the query string already removed.
# Anchoring on end-of-URL instead dropped nine real tests whose sitemap entries
# carry a search parameter - "pathology-test/hba1c?q=hba1c" and the like. The
# old script kept those but baked "?q=hba1c" into the test name, which is a
# quieter version of the same bug.
TEST_PATH = re.compile(
    r"^/(?:[a-z-]+/tests/|pathology-test/|radiology-tests/)?([^/]+)/?$"
)
CITY_SEGMENT = re.compile(r"https?://[^/]+/([a-z-]+)/tests/")

SKIP_SEGMENTS = frozenset({
    "sitemap", "checkout", "about-us", "faq", "offers", "terms-of-use",
    "dashboard", "recommendation", "uploadprescription", "esg", "blog",
})
# Booking and navigation pages that sit in the same path space as tests.
SKIP_PREFIXES = ("book-", "lp-", "campaign-")


def slug_to_name(slug: str) -> str:
    return re.sub(r"\s+", " ", slug.replace("-", " ")).strip()


def parse(texts: list[str], source: Source) -> ParseResult:
    """Names from one or more sitemap documents belonging to the same source.

    City landing pages are excluded by asking the site rather than by a
    hand-written blocklist: a slug that also appears as the city segment of a
    /{city}/tests/ URL is a city, not a test. 139 of them were being harvested
    as test names before this, and one reached the evaluation sample.
    """
    cities: set[str] = set()
    for text in texts:
        cities |= set(CITY_SEGMENT.findall(text))

    rows: list[RawRow] = []
    seen: set[str] = set()
    skipped = 0

    for text in texts:
        for url in LOC.findall(text):
            path = unquote(urlsplit(url.strip()).path)
            match = TEST_PATH.match(path)
            if not match:
                skipped += 1
                continue
            slug = match.group(1)
            if (slug in cities or slug in SKIP_SEGMENTS or slug.endswith(".xml")
                    or slug.startswith(SKIP_PREFIXES)):
                skipped += 1
                continue
            name = slug_to_name(slug)
            if len(name) < 2 or name.lower() in seen:
                continue
            seen.add(name.lower())
            rows.append(RawRow(raw_name=name, source_id=source.id,
                               as_of=source.as_of, display_ok=False))
    return ParseResult(rows, skipped=skipped)
