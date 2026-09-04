"""Load and validate the hand-curated taxonomy.

Validation is strict and fails loudly. The taxonomy is the one artefact in this
project that is not derived from anything - if it is wrong, every downstream
number is wrong, and nothing later in the pipeline can detect that. So the
errors below are all hard failures, not warnings.

The load-bearing check is the alias collision test. Two canonical tests sharing
a normalised alias means the matcher can be handed a name with no correct
answer available, and it will still confidently return one.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ratecard.names import alias_key
from ratecard.taxonomy.schema import (
    CanonicalTest,
    Category,
    Kind,
    Modality,
    Specimen,
)

DATA_DIR = Path(__file__).parent / "data"

ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_")

# `views` is meaningful only where a study is defined by how many projections
# were taken; `contrast` only where a contrast agent is an option at all.
_VIEWS_MODALITIES = {Modality.RADIOGRAPHY, Modality.MAMMOGRAPHY}
_CONTRAST_MODALITIES = {Modality.CT, Modality.MRI}


class ValidationError(Exception):
    """Raised when the taxonomy is internally inconsistent."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        joined = "\n  - ".join(problems)
        super().__init__(f"{len(problems)} taxonomy problem(s):\n  - {joined}")


@dataclass(frozen=True, slots=True)
class Warning_:
    test_id: str
    message: str


class Taxonomy:
    """An immutable, validated set of canonical tests plus its alias index."""

    def __init__(self, tests: dict[str, CanonicalTest], index: dict[str, str]) -> None:
        self._tests = tests
        self._index = index

    # -- container protocol ------------------------------------------------
    def __len__(self) -> int:
        return len(self._tests)

    def __iter__(self) -> Iterator[CanonicalTest]:
        return iter(self._tests.values())

    def __contains__(self, test_id: object) -> bool:
        return test_id in self._tests

    def __getitem__(self, test_id: str) -> CanonicalTest:
        return self._tests[test_id]

    # -- lookup ------------------------------------------------------------
    def get(self, test_id: str) -> CanonicalTest | None:
        return self._tests.get(test_id)

    def lookup(self, raw_name: str) -> CanonicalTest | None:
        """Exact resolution of a raw name via the alias index.

        This is the free 'pass 0' of the matcher: no fuzzy logic, no model, no
        chance of being wrong. Whatever this returns needs no review.
        """
        test_id = self._index.get(alias_key(raw_name))
        return self._tests.get(test_id) if test_id else None

    @property
    def alias_index(self) -> dict[str, str]:
        return dict(self._index)

    def by_category(self) -> dict[Category, list[CanonicalTest]]:
        out: dict[Category, list[CanonicalTest]] = {}
        for test in self._tests.values():
            out.setdefault(test.category, []).append(test)
        return out


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def _build(raw: dict[str, Any], source: Path, problems: list[str]) -> CanonicalTest | None:
    where = f"{source.name}:{raw.get('id', '<no id>')}"

    try:
        test_id = str(raw["id"])
        name = str(raw["name"])
        category = Category(raw["category"])
        kind = Kind(raw["kind"])
    except KeyError as exc:
        problems.append(f"{where}: missing required field {exc}")
        return None
    except ValueError as exc:
        problems.append(f"{where}: {exc}")
        return None

    specimen = Specimen(raw["specimen"]) if raw.get("specimen") else None
    modality = Modality(raw["modality"]) if raw.get("modality") else None

    return CanonicalTest(
        id=test_id,
        name=name,
        category=category,
        kind=kind,
        specimen=specimen,
        fasting_required=raw.get("fasting_required"),
        modality=modality,
        body_region=raw.get("body_region"),
        views=raw.get("views"),
        contrast=raw.get("contrast"),
        is_panel=bool(raw.get("is_panel", False)),
        analytes=_as_tuple(raw.get("analytes")),
        components=_as_tuple(raw.get("components")),
        distinct_from=_as_tuple(raw.get("distinct_from")),
        loinc=raw.get("loinc"),
        aliases=_as_tuple(raw.get("aliases")),
        notes=raw.get("notes"),
    )


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def _check_shape(test: CanonicalTest, problems: list[str]) -> None:
    where = test.id

    if not set(test.id) <= ID_CHARS:
        problems.append(f"{where}: id must be lowercase snake_case")
    if not test.name.strip():
        problems.append(f"{where}: name is empty")

    if test.kind is Kind.LAB:
        if test.specimen is None:
            problems.append(f"{where}: lab test has no specimen")
        for field_name in ("modality", "body_region", "views", "contrast"):
            if getattr(test, field_name) is not None:
                problems.append(f"{where}: lab test must not set {field_name}")
    else:
        if test.modality is None:
            problems.append(f"{where}: imaging study has no modality")
        for field_name in ("specimen", "fasting_required"):
            if getattr(test, field_name) is not None:
                problems.append(f"{where}: imaging study must not set {field_name}")
        if test.views is not None and test.modality not in _VIEWS_MODALITIES:
            problems.append(f"{where}: views is meaningless for modality {test.modality}")
        if test.contrast is not None and test.modality not in _CONTRAST_MODALITIES:
            problems.append(f"{where}: contrast is meaningless for modality {test.modality}")

    # A panel must say what it contains, or the analyte-count discriminator
    # that separates 'lipid profile' from 'lipid profile extended' is unusable.
    if test.is_panel and not test.analytes:
        problems.append(f"{where}: is_panel is true but no analytes are listed")
    if test.analytes and not test.is_panel:
        problems.append(f"{where}: analytes listed but is_panel is false")
    if test.components and not test.is_panel:
        problems.append(f"{where}: components listed but is_panel is false")

    if not test.aliases:
        problems.append(f"{where}: no aliases - at minimum list how the sources write it")


def _check_components(tests: dict[str, CanonicalTest], problems: list[str]) -> None:
    for test in tests.values():
        for component in test.components:
            if component not in tests:
                problems.append(f"{test.id}: component '{component}' is not a canonical id")
            elif component == test.id:
                problems.append(f"{test.id}: lists itself as a component")
            elif test.id in tests[component].components:
                problems.append(f"{test.id}: component cycle with '{component}'")

        for other in test.distinct_from:
            if other not in tests:
                problems.append(f"{test.id}: distinct_from '{other}' is not a canonical id")
            elif other == test.id:
                problems.append(f"{test.id}: declares itself distinct from itself")


def _build_index(tests: dict[str, CanonicalTest], problems: list[str]) -> dict[str, str]:
    """Map every normalised name and alias to exactly one canonical id."""
    index: dict[str, str] = {}
    origin: dict[str, str] = {}

    for test in tests.values():
        for surface in (test.name, *test.aliases):
            key = alias_key(surface)
            if not key:
                problems.append(f"{test.id}: alias '{surface}' normalises to empty string")
                continue
            if key in index and index[key] != test.id:
                problems.append(
                    f"alias collision on '{key}': "
                    f"{index[key]} (via '{origin[key]}') and {test.id} (via '{surface}')"
                )
                continue
            index[key] = test.id
            origin[key] = surface

    return index


def collect_warnings(taxonomy: Taxonomy) -> list[Warning_]:
    """Non-fatal quality signals. Reported by the CLI, never raised."""
    out: list[Warning_] = []
    for test in taxonomy:
        if test.kind is Kind.LAB and not test.loinc:
            out.append(Warning_(test.id, "no LOINC code"))
        if len(test.aliases) < 3:
            out.append(Warning_(test.id, f"only {len(test.aliases)} alias(es)"))
        if test.is_panel and not test.components:
            out.append(Warning_(test.id, "panel declares no separately-orderable components"))
    return out


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def load(data_dir: Path | str | None = None) -> Taxonomy:
    """Read every YAML file in `data_dir`, validate, and return the taxonomy."""
    directory = Path(data_dir) if data_dir else DATA_DIR
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise ValidationError([f"no taxonomy YAML files found in {directory}"])

    problems: list[str] = []
    tests: dict[str, CanonicalTest] = {}
    seen_names: dict[str, str] = {}

    for path in files:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(payload, list):
            problems.append(f"{path.name}: top level must be a list of tests")
            continue

        for raw in payload:
            if not isinstance(raw, dict):
                problems.append(f"{path.name}: entry is not a mapping: {raw!r}")
                continue
            test = _build(raw, path, problems)
            if test is None:
                continue
            if test.id in tests:
                problems.append(f"duplicate id '{test.id}' in {path.name}")
                continue
            lowered = test.name.strip().lower()
            if lowered in seen_names:
                problems.append(f"duplicate name '{test.name}' ({seen_names[lowered]}, {test.id})")
            seen_names[lowered] = test.id
            tests[test.id] = test
            _check_shape(test, problems)

    _check_components(tests, problems)
    index = _build_index(tests, problems)

    if problems:
        raise ValidationError(problems)

    return Taxonomy(tests, index)
