"""Load and validate the source registry.

Validation here is mostly about governance rather than types. The checks that
matter are the ones encoding what Phase 00 got wrong:

  - a source that may be displayed must say which city it is for, because the
    census published Guwahati prices as Bengaluru ones
  - a source carrying prices must name its comparison tier, and that tier must
    actually be one of its columns
  - a PDF must pin a sha256, or the fetcher cannot tell a reissue from a cache
  - every source must carry a licence note, so that "am I allowed to use this"
    is answered deliberately and not by omission
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ratecard.registry.schema import Format, Refresh, Source

DATA_DIR = Path(__file__).parent / "data"
ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_")


class RegistryError(Exception):
    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        joined = "\n  - ".join(problems)
        super().__init__(f"{len(problems)} registry problem(s):\n  - {joined}")


class Registry:
    def __init__(self, sources: dict[str, Source]) -> None:
        self._sources = sources

    def __len__(self) -> int:
        return len(self._sources)

    def __iter__(self) -> Iterator[Source]:
        return iter(self._sources.values())

    def __contains__(self, source_id: object) -> bool:
        return source_id in self._sources

    def __getitem__(self, source_id: str) -> Source:
        return self._sources[source_id]

    def get(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def for_city(self, city: str) -> list[Source]:
        return [s for s in self if s.city and s.city.lower() == city.lower()]

    def displayable(self) -> list[Source]:
        """Sources whose prices may reach a public comparison."""
        return [s for s in self if s.display_ok]


def _as_date(value: Any, field: str, where: str, problems: list[str]) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        problems.append(f"{where}: {field} is not an ISO date: {value!r}")
        return None


def _build(raw: dict[str, Any], problems: list[str]) -> Source | None:
    where = raw.get("id", "<no id>")
    try:
        source = Source(
            id=str(raw["id"]),
            publisher=str(raw["publisher"]),
            url=str(raw["url"]),
            format=Format(raw["format"]),
            parser=str(raw["parser"]),
            city=raw.get("city"),
            unit=raw.get("unit"),
            sha256=raw.get("sha256"),
            as_of=_as_date(raw.get("as_of"), "as_of", where, problems),
            retrieved=_as_date(raw.get("retrieved"), "retrieved", where, problems),
            refresh=Refresh(raw.get("refresh", "unknown")),
            tiers=tuple(raw.get("tiers") or ()),
            comparison_tier=raw.get("comparison_tier"),
            display_ok=bool(raw.get("display_ok", False)),
            licence_note=str(raw.get("licence_note", "")),
            notes=raw.get("notes"),
        )
    except KeyError as exc:
        problems.append(f"{where}: missing required field {exc}")
        return None
    except ValueError as exc:
        problems.append(f"{where}: {exc}")
        return None
    return source


def _check(source: Source, problems: list[str]) -> None:
    where = source.id

    if not set(source.id) <= ID_CHARS:
        problems.append(f"{where}: id must be lowercase snake_case")
    if not source.url.startswith("https://"):
        problems.append(f"{where}: url must be https")

    # Governance, not typing. Each of these is a mistake already made once.
    if not source.licence_note.strip():
        problems.append(
            f"{where}: licence_note is empty. Record why this source may be used - "
            f"robots.txt, terms, or that it is a government publication."
        )
    if source.display_ok and not source.city:
        problems.append(
            f"{where}: display_ok is true but no city is set. The census published "
            f"Guwahati prices as Bengaluru ones; a displayable price must say where."
        )
    if source.format is Format.PDF and not source.sha256:
        problems.append(
            f"{where}: a PDF must pin a sha256, or the fetcher cannot tell a "
            f"reissued document from a cached one."
        )

    if source.carries_prices:
        if not source.comparison_tier:
            problems.append(f"{where}: has price tiers but names no comparison_tier")
        elif source.comparison_tier not in source.tiers:
            problems.append(
                f"{where}: comparison_tier {source.comparison_tier!r} is not one of "
                f"its tiers {list(source.tiers)}"
            )
    elif source.display_ok:
        problems.append(
            f"{where}: display_ok is true but the source carries no price tiers"
        )


def load(data_dir: Path | str | None = None) -> Registry:
    directory = Path(data_dir) if data_dir else DATA_DIR
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise RegistryError([f"no registry YAML found in {directory}"])

    problems: list[str] = []
    sources: dict[str, Source] = {}

    for path in files:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(payload, list):
            problems.append(f"{path.name}: top level must be a list of sources")
            continue
        for raw in payload:
            if not isinstance(raw, dict):
                problems.append(f"{path.name}: entry is not a mapping: {raw!r}")
                continue
            source = _build(raw, problems)
            if source is None:
                continue
            if source.id in sources:
                problems.append(f"duplicate source id '{source.id}'")
                continue
            sources[source.id] = source
            _check(source, problems)

    if problems:
        raise RegistryError(problems)
    return Registry(sources)
