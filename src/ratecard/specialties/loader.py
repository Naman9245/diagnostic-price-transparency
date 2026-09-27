"""Load and validate the specialty list.

The test taxonomy's rules carry over: every alias names exactly one specialty,
and anything that could name two is not an alias. What is new is the second
kind of surface form, `related_terms` - words like "kidney" or "oncologist"
that point at several specialties. They suggest and never resolve, so the
check that matters most here is that no related term is also an alias. If one
were, "kidney" would quietly resolve to one specialty while claiming to offer a
choice.

Stdlib plus PyYAML only: `ratecard validate` and `ratecard specialty` run on a
bare machine, like the rest of Phase 01.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from ratecard.names import alias_key

DATA = Path(__file__).parent / "data" / "specialties.yaml"

ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_")

# How departments are written around a specialty name: "Department of
# Cardiology", "CARDIOLOGY OPD", "Consultant Physician". None of them can tell
# two specialties apart. "doctor" and "specialist" are NOT here: they are part
# of "skin doctor" and "heart specialist", and stripping them would turn those
# aliases into the related terms "skin" and "heart".
_DEPARTMENT_WORDS = frozenset({
    "department", "dept", "opd", "clinic", "consultation", "consultant",
    "unit", "services", "service",
})


def specialty_key(raw: str) -> str:
    """The lookup key for a specialty name: `alias_key` without department words.

    >>> specialty_key("Department of Cardiology")
    'cardiology'
    >>> specialty_key("PAEDIATRIC SURGERY OPD")
    'pediatric surgery'
    """
    return " ".join(t for t in alias_key(raw).split() if t not in _DEPARTMENT_WORDS)


class Category(StrEnum):
    MEDICAL = "medical"
    SURGICAL = "surgical"
    DENTAL = "dental"
    # Not doctors: physiotherapists, psychologists, dietitians, audiologists.
    ALLIED_HEALTH = "allied_health"


@dataclass(frozen=True, slots=True)
class Specialty:
    id: str
    name: str
    # How the doctor is described: "Cardiologist" for Cardiology.
    practitioner: str
    category: Category
    aliases: tuple[str, ...] = ()
    related_terms: tuple[str, ...] = ()
    distinct_from: tuple[str, ...] = ()
    notes: str | None = None

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.id} ({self.name})"


class SpecialtyError(Exception):
    """Raised when the specialty list is internally inconsistent."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        joined = "\n  - ".join(problems)
        super().__init__(f"{len(problems)} specialty problem(s):\n  - {joined}")


class Specialties:
    """An immutable, validated specialty list with its two indexes."""

    def __init__(self, specialties: dict[str, Specialty], index: dict[str, str],
                 terms: dict[str, tuple[str, ...]]) -> None:
        self._specialties = specialties
        self._index = index
        self._terms = terms

    def __len__(self) -> int:
        return len(self._specialties)

    def __iter__(self) -> Iterator[Specialty]:
        return iter(self._specialties.values())

    def __contains__(self, specialty_id: object) -> bool:
        return specialty_id in self._specialties

    def __getitem__(self, specialty_id: str) -> Specialty:
        return self._specialties[specialty_id]

    def get(self, specialty_id: str) -> Specialty | None:
        return self._specialties.get(specialty_id)

    def lookup(self, raw: str) -> Specialty | None:
        """Exact resolution through the alias index. Never guesses."""
        specialty_id = self._index.get(specialty_key(raw))
        return self._specialties.get(specialty_id) if specialty_id else None

    def suggest(self, raw: str) -> list[Specialty]:
        """Specialties a name points at without naming: every related term that
        appears in it as whole words. A list to choose from, never an answer -
        "kidney doctor" suggests nephrology and urology and resolves to neither.
        """
        words = f" {specialty_key(raw)} "
        found = {sid for term, ids in self._terms.items() if f" {term} " in words
                 for sid in ids}
        return sorted((self._specialties[s] for s in found), key=lambda s: s.name)

    @property
    def alias_index(self) -> dict[str, str]:
        """Every key that resolves, mapped to its one specialty."""
        return dict(self._index)

    @property
    def term_index(self) -> dict[str, tuple[str, ...]]:
        """Every related-term key, mapped to all the specialties it suggests."""
        return dict(self._terms)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def _build(raw: dict[str, Any], problems: list[str]) -> Specialty | None:
    where = raw.get("id", "<no id>")
    try:
        return Specialty(
            id=str(raw["id"]),
            name=str(raw["name"]),
            practitioner=str(raw["practitioner"]),
            category=Category(raw["category"]),
            aliases=_as_tuple(raw.get("aliases")),
            related_terms=_as_tuple(raw.get("related_terms")),
            distinct_from=_as_tuple(raw.get("distinct_from")),
            notes=raw.get("notes"),
        )
    except KeyError as exc:
        problems.append(f"{where}: missing required field {exc}")
    except ValueError as exc:
        problems.append(f"{where}: {exc}")
    return None


def _check(specialties: dict[str, Specialty], problems: list[str]) -> None:
    for s in specialties.values():
        if not set(s.id) <= ID_CHARS:
            problems.append(f"{s.id}: id must be lowercase snake_case")
        if not s.name.strip():
            problems.append(f"{s.id}: name is empty")
        if not s.practitioner.strip():
            problems.append(f"{s.id}: practitioner is empty")
        if not s.aliases:
            problems.append(f"{s.id}: no aliases")
        for other in s.distinct_from:
            if other not in specialties:
                problems.append(f"{s.id}: distinct_from '{other}' is not a specialty id")
            elif other == s.id:
                problems.append(f"{s.id}: declares itself distinct from itself")


def _build_indexes(specialties: dict[str, Specialty], problems: list[str],
                   ) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    index: dict[str, str] = {}
    origin: dict[str, str] = {}
    for s in specialties.values():
        for surface in (s.name, s.practitioner, *s.aliases):
            key = specialty_key(surface)
            if not key:
                problems.append(f"{s.id}: '{surface}' normalises to an empty string")
                continue
            if key in index and index[key] != s.id:
                problems.append(f"alias collision on '{key}': {index[key]} (via "
                                f"'{origin[key]}') and {s.id} (via '{surface}')")
                continue
            index[key] = s.id
            origin[key] = surface

    terms: dict[str, list[str]] = {}
    for s in specialties.values():
        for term in s.related_terms:
            key = specialty_key(term)
            if not key:
                problems.append(f"{s.id}: related term '{term}' normalises to an empty string")
                continue
            # The load-bearing check. A term that is also an alias would resolve
            # to one specialty while claiming to offer a choice.
            if key in index:
                problems.append(f"{s.id}: related term '{term}' is also an alias of "
                                f"{index[key]}; a word either names one specialty "
                                f"or suggests several, never both")
                continue
            ids = terms.setdefault(key, [])
            if s.id not in ids:
                ids.append(s.id)
    return index, {k: tuple(v) for k, v in terms.items()}


def load(path: Path | str | None = None) -> Specialties:
    """Read the specialty YAML, validate it, and return the list."""
    source = Path(path) if path else DATA
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or []
    if not isinstance(payload, list):
        raise SpecialtyError([f"{source.name}: top level must be a list of specialties"])

    problems: list[str] = []
    specialties: dict[str, Specialty] = {}
    seen_names: dict[str, str] = {}
    for raw in payload:
        if not isinstance(raw, dict):
            problems.append(f"entry is not a mapping: {raw!r}")
            continue
        specialty = _build(raw, problems)
        if specialty is None:
            continue
        if specialty.id in specialties:
            problems.append(f"duplicate id '{specialty.id}'")
            continue
        lowered = specialty.name.strip().lower()
        if lowered in seen_names:
            problems.append(f"duplicate name '{specialty.name}' "
                            f"({seen_names[lowered]}, {specialty.id})")
        seen_names[lowered] = specialty.id
        specialties[specialty.id] = specialty

    _check(specialties, problems)
    index, terms = _build_indexes(specialties, problems)
    if problems:
        raise SpecialtyError(problems)
    return Specialties(specialties, index, terms)
