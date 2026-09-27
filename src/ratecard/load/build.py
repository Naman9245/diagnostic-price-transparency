"""Stage 5, the half that needs no database.

Turns the taxonomy, the registry and a parsed corpus into the records the
database holds. Pure functions: `db.py` writes exactly what these return and
decides nothing, so every rule about what may become a public price is tested
here without Postgres.

The rules, in the order they bite:

- **Only a displayable source is loaded at all.** The registry is the authority,
  not the row - a corpus row claiming `display_ok=True` for a source the
  registry forbids is dropped. Guwahati prices cannot reach the database, so
  they cannot reach a view by any route.
- **Only the comparison tier is loaded.** Tier vocabulary is per-document; the
  OPD walk-in rate is the only column comparable across publishers.
- **`needs_review` is the matcher's, unchanged.** Only an exact alias hit is
  trusted. The database marks a row public from this flag; it is never
  recomputed or loosened here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from ratecard.registry import Registry
from ratecard.specialties import Specialties
from ratecard.taxonomy import Taxonomy

PROVIDERS = Path(__file__).resolve().parent / "data" / "providers.yaml"
KINDS = frozenset({"hospital", "lab", "imaging", "clinic"})


class LoadError(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__(f"{len(problems)} problem(s)")
        self.problems = problems


class MatchLike(Protocol):
    test_id: str | None
    confidence: float
    method: str

    @property
    def needs_review(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class Provider:
    slug: str
    name: str
    kind: str
    city: str
    lat: float
    lng: float
    sources: tuple[str, ...]
    brand: str | None = None
    locality: str | None = None
    address: str | None = None
    phone: str | None = None


@dataclass(frozen=True, slots=True)
class PriceRecord:
    source_id: str
    provider_slug: str
    raw_test_name: str
    service_code: str | None
    price_inr: int
    price_tier: str
    canonical_test_id: str | None
    match_confidence: float
    match_method: str
    needs_review: bool

    @property
    def public(self) -> bool:
        """What the database's policy will decide. Mirrored here for reporting
        only - the database is what enforces it."""
        return self.canonical_test_id is not None and not self.needs_review


@dataclass
class PriceBatch:
    records: list[PriceRecord] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)

    @property
    def public(self) -> int:
        return sum(1 for r in self.records if r.public)


def load_providers(registry: Registry, path: Path | str | None = None) -> list[Provider]:
    """Read and validate providers.yaml against the registry. Raises LoadError."""
    raw = yaml.safe_load(Path(path or PROVIDERS).read_text(encoding="utf-8")) or []
    problems: list[str] = []
    providers: list[Provider] = []
    owner: dict[str, str] = {}

    for n, entry in enumerate(raw):
        where = entry.get("slug") or f"entry {n}"
        missing = [k for k in ("slug", "name", "kind", "city", "lat", "lng", "sources")
                   if entry.get(k) in (None, "", [])]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        if entry["kind"] not in KINDS:
            problems.append(f"{where}: kind {entry['kind']!r} is not one of {sorted(KINDS)}")
        lat, lng = float(entry["lat"]), float(entry["lng"])
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            problems.append(f"{where}: coordinates out of range ({lat}, {lng})")

        for source_id in entry["sources"]:
            source = registry.get(source_id)
            if source is None:
                problems.append(f"{where}: unknown source {source_id!r}")
            elif not source.display_ok:
                problems.append(f"{where}: source {source_id!r} is display_ok=false; "
                                f"a provider only exists here to carry displayable prices")
            elif source.city and source.city.lower() != str(entry["city"]).lower():
                problems.append(f"{where}: source {source_id!r} is in {source.city}, "
                                f"provider is in {entry['city']}")
            if source_id in owner:
                problems.append(f"{where}: source {source_id!r} already belongs to "
                                f"{owner[source_id]}")
            owner[source_id] = entry["slug"]

        providers.append(Provider(
            slug=entry["slug"], name=entry["name"], kind=entry["kind"], city=entry["city"],
            lat=lat, lng=lng, sources=tuple(entry["sources"]), brand=entry.get("brand"),
            locality=entry.get("locality"), address=entry.get("address"),
            phone=entry.get("phone"),
        ))

    slugs = Counter(p.slug for p in providers)
    problems += [f"{slug}: duplicate slug" for slug, count in slugs.items() if count > 1]
    for source in registry.displayable():
        if source.id not in owner:
            problems.append(f"source {source.id!r} is displayable but no provider "
                            f"in providers.yaml charges its prices")
    if problems:
        raise LoadError(problems)
    return providers


def canonical_test_records(taxonomy: Taxonomy) -> list[dict[str, Any]]:
    return [{
        "id": t.id,
        "name": t.name,
        "category": str(t.category),
        "kind": str(t.kind),
        "loinc_code": t.loinc,
        "specimen": str(t.specimen) if t.specimen else None,
        "is_panel": t.is_panel,
    } for t in sorted(taxonomy, key=lambda t: t.id)]


def alias_records(taxonomy: Taxonomy) -> list[tuple[str, str]]:
    """Every indexed surface form. Search resolves through these and nothing
    fuzzier - the matcher never runs at query time."""
    return sorted(taxonomy.alias_index.items())


def specialty_records(specialties: Specialties) -> list[dict[str, Any]]:
    return [{
        "id": s.id,
        "name": s.name,
        "practitioner": s.practitioner,
        "category": str(s.category),
    } for s in sorted(specialties, key=lambda s: s.id)]


def specialty_alias_records(specialties: Specialties) -> list[tuple[str, str]]:
    """Surface forms that resolve, each to exactly one specialty."""
    return sorted(specialties.alias_index.items())


def specialty_term_records(specialties: Specialties) -> list[tuple[str, str]]:
    """Related terms, one row per specialty they point at. They only suggest."""
    return sorted((term, sid) for term, ids in specialties.term_index.items() for sid in ids)


def source_records(registry: Registry, providers: list[Provider]) -> list[dict[str, Any]]:
    slug_of = {sid: p.slug for p in providers for sid in p.sources}
    return [{
        "id": s.id,
        "provider_slug": slug_of[s.id],
        "publisher": s.publisher,
        "unit": s.unit,
        "city": s.city,
        "url": s.url,
        "doc_type": "published_rate_card",
        "sha256": s.sha256,
        "as_of": s.as_of,
        "retrieved": s.retrieved,
        "licence_note": s.licence_note.strip(),
        "comparison_tier": s.comparison_tier,
    } for s in registry.displayable()]


def price_records(rows: Iterable[Mapping[str, str]], matches: Mapping[str, MatchLike],
                  registry: Registry, providers: list[Provider]) -> PriceBatch:
    """Corpus rows -> price observations. `matches` is keyed by stripped raw name."""
    slug_of = {sid: p.slug for p in providers for sid in p.sources}
    batch = PriceBatch()

    for row in rows:
        source = registry.get(row["source"])
        if source is None or not source.display_ok:
            batch.skipped["source not displayable"] += 1
            continue
        if row.get("tier") != source.comparison_tier:
            batch.skipped["not the comparison tier"] += 1
            continue
        price = (row.get("price") or "").replace(",", "").strip()
        if not price:
            batch.skipped["no price"] += 1
            continue
        if not price.isdigit():
            batch.skipped["unreadable price"] += 1
            continue

        name = row["raw_name"].strip()
        match = matches[name]
        batch.records.append(PriceRecord(
            source_id=source.id,
            provider_slug=slug_of[source.id],
            raw_test_name=name,
            service_code=row.get("service_code") or None,
            price_inr=int(price),
            price_tier=row["tier"],
            canonical_test_id=match.test_id,
            match_confidence=round(float(match.confidence), 1),
            match_method=match.method,
            needs_review=match.needs_review,
        ))
    return batch
