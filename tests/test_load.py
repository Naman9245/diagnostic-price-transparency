"""Stage 5, build half: what may become a public price, tested without Postgres."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from ratecard.load import (
    LoadError,
    alias_records,
    canonical_test_records,
    load_providers,
    price_records,
    source_records,
    specialty_alias_records,
    specialty_records,
    specialty_term_records,
)
from ratecard.registry import load as load_registry
from ratecard.specialties import load as load_specialties
from ratecard.taxonomy import load as load_taxonomy

BENGALURU = "narayana_mazumdar_shaw_bengaluru"
GUWAHATI = "narayana_guwahati"


@dataclass
class FakeMatch:
    test_id: str | None
    confidence: float
    method: str

    @property
    def needs_review(self) -> bool:
        return self.method != "exact"


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.fixture(scope="module")
def providers(registry):
    return load_providers(registry)


def row(name="CBC", source=BENGALURU, price="450", tier="OPD", display_ok="True", code=""):
    return {"raw_name": name, "source": source, "price": price, "tier": tier,
            "service_code": code, "service_type": "", "as_of": "2024-01-01",
            "display_ok": display_ok}


EXACT = {"CBC": FakeMatch("cbc", 100.0, "exact")}


def test_packaged_providers_file_is_valid(providers):
    assert [p.slug for p in providers] == ["narayana-mazumdar-shaw-bengaluru"]
    assert providers[0].sources == (BENGALURU,)


def test_a_source_the_registry_forbids_never_becomes_a_row(registry, providers):
    """The registry is the authority. A corpus row claiming display_ok=True for
    Guwahati is the census mistake again, and must be dropped."""
    batch = price_records([row(source=GUWAHATI, display_ok="True")], EXACT, registry, providers)
    assert batch.records == []
    assert batch.skipped["source not displayable"] == 1


def test_needs_review_is_carried_not_recomputed(registry, providers):
    matches = {"CBC": FakeMatch("cbc", 100.0, "exact"),
               "COMPLETE BLOOD PICTURE": FakeMatch("cbc", 97.0, "lexical")}
    batch = price_records([row(), row(name="COMPLETE BLOOD PICTURE", code="X1")],
                          matches, registry, providers)
    exact, lexical = batch.records
    assert (exact.needs_review, exact.public) == (False, True)
    # 97 is a high score and still a guess: stored, never public.
    assert (lexical.needs_review, lexical.public) == (True, False)
    assert batch.public == 1


def test_an_abstention_is_stored_but_never_public(registry, providers):
    matches = {"ABOVE ELBOW AMPUTATION": FakeMatch(None, 0.0, "abstain_no_candidate")}
    batch = price_records([row(name="ABOVE ELBOW AMPUTATION")], matches, registry, providers)
    assert batch.records[0].canonical_test_id is None
    assert not batch.records[0].public


def test_only_the_comparison_tier_is_loaded(registry, providers):
    batch = price_records([row(tier="PLATINUM SUITE")], EXACT, registry, providers)
    assert batch.records == []
    assert batch.skipped["not the comparison tier"] == 1


@pytest.mark.parametrize("price, reason", [("", "no price"), ("on request", "unreadable price")])
def test_rows_without_a_usable_price_are_counted_not_guessed(registry, providers, price, reason):
    batch = price_records([row(price=price)], EXACT, registry, providers)
    assert batch.records == []
    assert batch.skipped[reason] == 1


def test_prices_with_thousands_separators_parse(registry, providers):
    batch = price_records([row(price="12,500")], EXACT, registry, providers)
    assert batch.records[0].price_inr == 12500


def test_raw_names_are_matched_stripped(registry, providers):
    batch = price_records([row(name="  CBC ")], EXACT, registry, providers)
    assert batch.records[0].raw_test_name == "CBC"


def _write(tmp_path, text):
    path = tmp_path / "providers.yaml"
    path.write_text(text, encoding="utf-8")
    return path


GOOD = """
- slug: x
  name: X
  kind: hospital
  city: Bengaluru
  lat: 12.9
  lng: 77.6
  sources: [narayana_mazumdar_shaw_bengaluru]
"""


def test_a_provider_needs_coordinates(registry, tmp_path):
    with pytest.raises(LoadError, match="problem") as exc:
        load_providers(registry, _write(tmp_path, GOOD.replace("  lat: 12.9\n", "")))
    assert any("missing lat" in p for p in exc.value.problems)


def test_a_provider_cannot_carry_a_non_displayable_source(registry, tmp_path):
    text = GOOD.replace("[narayana_mazumdar_shaw_bengaluru]",
                        "[narayana_mazumdar_shaw_bengaluru, narayana_guwahati]")
    with pytest.raises(LoadError) as exc:
        load_providers(registry, _write(tmp_path, text))
    assert any("display_ok=false" in p for p in exc.value.problems)


def test_every_displayable_source_needs_a_provider(registry, tmp_path):
    text = GOOD.replace("[narayana_mazumdar_shaw_bengaluru]", "[]")
    with pytest.raises(LoadError) as exc:
        load_providers(registry, _write(tmp_path, text))
    assert any("no provider" in p for p in exc.value.problems)


def test_provider_city_must_match_its_sources(registry, tmp_path):
    with pytest.raises(LoadError) as exc:
        load_providers(registry, _write(tmp_path, GOOD.replace("Bengaluru", "Guwahati")))
    assert any("is in Bengaluru" in p for p in exc.value.problems)


def test_reference_records_cover_the_whole_taxonomy(registry, providers):
    taxonomy = load_taxonomy()
    assert len(canonical_test_records(taxonomy)) == len(taxonomy)
    assert dict(alias_records(taxonomy)) == taxonomy.alias_index
    sources = source_records(registry, providers)
    assert [s["id"] for s in sources] == [BENGALURU]
    assert sources[0]["as_of"] is not None and sources[0]["sha256"]


def test_building_records_never_imports_psycopg():
    """Optional deps stay optional: only writing needs the database driver."""
    code = ("import sys, ratecard.load, ratecard.cli; "
            "sys.exit(1 if 'psycopg' in sys.modules else 0)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, check=False,
                            cwd=Path(__file__).resolve().parent.parent)
    assert result.returncode == 0


def test_specialty_records_cover_the_whole_list():
    specialties = load_specialties()
    assert len(specialty_records(specialties)) == len(specialties)
    assert dict(specialty_alias_records(specialties)) == specialties.alias_index
    terms = specialty_term_records(specialties)
    assert len(terms) == len(set(terms)) == sum(len(v) for v in specialties.term_index.values())
    # "kidney" points at two specialties, so it is two rows.
    assert {sid for term, sid in terms if term == "kidney"} == {"nephrology", "urology"}
