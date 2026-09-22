"""Stage 3 - turn a fetched document into rows carrying their provenance.

Adapters are looked up by the registry's `parser` field, so a new source in an
already-supported format needs a YAML entry and no code at all. A genuinely new
format needs one function registered here.
"""

from ratecard.parse import narayana_pdf, sitemap_slug
from ratecard.parse.rows import FIELDS, RawRow

#: parser name (as written in the registry) -> adapter module
PARSERS = {
    "narayana_pdf": narayana_pdf,
    "sitemap_slug": sitemap_slug,
}


def get(name: str):
    """Adapter for a registry `parser` value."""
    try:
        return PARSERS[name]
    except KeyError:
        raise KeyError(
            f"no parser named {name!r}. Known: {', '.join(sorted(PARSERS))}. "
            f"A new format needs an adapter module registered in parse/__init__.py."
        ) from None


__all__ = ["FIELDS", "PARSERS", "RawRow", "get", "narayana_pdf", "sitemap_slug"]
