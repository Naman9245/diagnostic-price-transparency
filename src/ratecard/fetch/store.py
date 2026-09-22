"""Stage 2 - the immutable raw store.

One rule, and everything here exists to enforce it: **a document already in the
store is never overwritten.** The parsers are written against exact documents -
the 11-column Bengaluru layout, the 8-column Guwahati one - so a publisher
reissuing a file is an event that must stop the pipeline and be looked at, not
something to absorb silently and hope the columns held.

This is lifted from `scripts/phase00_seed_corpus.py`, where the same logic was
correct but hardcoded to two known PDFs. Here it is driven by the registry, so
adding a source is a YAML entry rather than a code change.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ratecard.registry import Format, Source

UA = "ratecard-research/0.1 (student project; contact via repo)"
POLITE_PAUSE = 1.0


class SourceChanged(RuntimeError):
    """A publisher's document no longer matches the hash it was parsed against."""


@dataclass(frozen=True, slots=True)
class Fetched:
    source_id: str
    path: Path
    sha256: str
    from_cache: bool


class RawStore:
    """Content-addressed-ish store: one canonical path per source id."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, source: Source) -> Path:
        suffix = {Format.PDF: ".pdf", Format.SITEMAP: ".xml", Format.HTML: ".html"}[
            source.format
        ]
        return self.root / f"{source.id}{suffix}"

    def dated_sidecar(self, source: Source) -> Path:
        target = self.path_for(source)
        stamp = datetime.now(UTC).date().isoformat()
        return target.with_name(f"{target.stem}.fetched-{stamp}{target.suffix}")

    # -- verification ----------------------------------------------------
    def verify(self, source: Source) -> str:
        """sha256 of what is on disk, checked against the registry's pin."""
        target = self.path_for(source)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if source.sha256 and digest != source.sha256:
            raise SourceChanged(
                f"{target.name} on disk does not match the registry pin.\n"
                f"  expected {source.sha256}\n"
                f"  on disk  {digest}\n"
                f"  This is not the document the parser was written against. "
                f"Delete it and re-fetch, or update the registry."
            )
        return digest

    def _place(self, source: Source, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        target = self.path_for(source)

        # No pin means the source is expected to drift - sitemaps grow as
        # catalogues do - so there is nothing to betray by writing it.
        if not source.sha256 or digest == source.sha256:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return digest

        sidecar = self.dated_sidecar(source)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(data)
        raise SourceChanged(
            f"{source.id} has changed at the publisher.\n"
            f"  expected sha256 {source.sha256}\n"
            f"  received sha256 {digest}\n"
            f"  The new document is at {sidecar}; {target.name} is untouched.\n"
            f"  Inspect it, confirm the table layout, then update the registry "
            f"pin and rename the sidecar into place."
        )

    # -- fetching --------------------------------------------------------
    def fetch(self, source: Source, client, force: bool = False) -> Fetched:
        target = self.path_for(source)
        if target.exists() and not force:
            return Fetched(source.id, target, self.verify(source), from_cache=True)

        response = client.get(source.url)
        response.raise_for_status()
        digest = self._place(source, response.content)
        return Fetched(source.id, target, digest, from_cache=False)


def fetch_all(sources, store: RawStore, force: bool = False, client=None):
    """Fetch every source, pausing between live requests to be a polite guest."""
    import httpx

    owned = client is None
    client = client or httpx.Client(
        headers={"User-Agent": UA}, follow_redirects=True, timeout=120
    )
    try:
        for source in sources:
            result = store.fetch(source, client, force=force)
            yield result
            if not result.from_cache:
                time.sleep(POLITE_PAUSE)
    finally:
        if owned:
            client.close()
