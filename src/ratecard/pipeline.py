"""Stages 1-3 wired together: registry -> fetch -> parse -> rows.

The whole point of this module is that adding a source in an already-supported
format is a YAML entry and nothing else. `scripts/phase00_seed_corpus.py` did
the same work with the sources hardcoded; this reads them.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from ratecard import parse as adapters
from ratecard.fetch import RawStore
from ratecard.fetch.store import POLITE_PAUSE
from ratecard.parse.rows import RawRow
from ratecard.registry import Format, Registry, Source

# A sitemap that points at further sitemaps rather than at pages. Detected by
# what the <loc> entries are, not by the wrapper element: Redcliffe publishes
# its index as a <urlset> with the child sitemaps listed among ordinary page
# URLs, so requiring <sitemapindex> found nothing and harvested 24 names
# instead of 2,215.
CHILD_LOC = re.compile(r"<loc>([^<]+\.xml)</loc>", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Ingested:
    source_id: str
    rows: list[RawRow]
    unparsed: int
    documents: int
    skipped: int = 0


def child_sitemaps(text: str, limit: int = 20) -> list[str]:
    """Child sitemap URLs, or empty for an ordinary sitemap of pages."""
    return CHILD_LOC.findall(text)[:limit]


def documents_for(source: Source, store: RawStore, client=None) -> list[str]:
    """Every text document belonging to a source.

    Usually one. A sitemap index is the exception: Redcliffe's points at nine
    children, and the names live in those rather than in the index.
    """
    primary = store.path_for(source).read_text(encoding="utf-8", errors="replace")
    if source.format is not Format.SITEMAP:
        return [primary]

    children = child_sitemaps(primary)
    if not children:
        return [primary]

    # The index itself is dropped once children are found. Redcliffe's lists
    # the child sitemaps alongside ordinary nav pages - about-us, faq, offers -
    # which would otherwise be harvested as though they were test names. The
    # tests live in the children.
    directory = store.root / source.id
    directory.mkdir(parents=True, exist_ok=True)
    texts: list[str] = []
    for n, url in enumerate(children):
        path = directory / f"{n:02d}.xml"
        if not path.exists():
            if client is None:
                continue  # offline: use whatever is already cached
            response = client.get(url)
            response.raise_for_status()
            path.write_bytes(response.content)
            time.sleep(POLITE_PAUSE)
        texts.append(path.read_text(encoding="utf-8", errors="replace"))
    return texts


def pdf_text(source: Source, store: RawStore, interim: Path) -> str:
    """Extracted text for a PDF source, cached - extraction is slow."""
    cache = interim / f"{source.id}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")

    from pypdf import PdfReader

    reader = PdfReader(store.path_for(source))
    text = "".join(
        f"\n<<<PAGE {i + 1}>>>\n" + (page.extract_text() or "")
        for i, page in enumerate(reader.pages)
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def ingest(source: Source, store: RawStore, interim: Path, client=None) -> Ingested:
    """One source, fetched already, through its adapter."""
    adapter = adapters.get(source.parser)

    if source.format is Format.PDF:
        result = adapter.parse(pdf_text(source, store, interim), source)
        return Ingested(source.id, result.rows, result.unparsed, 1, result.skipped)

    texts = documents_for(source, store, client)
    result = adapter.parse(texts, source)
    return Ingested(source.id, result.rows, result.unparsed, len(texts), result.skipped)


def ingest_all(registry: Registry, store: RawStore, interim: Path, client=None):
    for source in registry:
        yield ingest(source, store, interim, client)
