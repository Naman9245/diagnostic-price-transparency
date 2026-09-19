"""Stage 1. The validation rules here are governance, not typing - each one
encodes a mistake the project has already made."""

import pytest
import yaml

from ratecard.registry import Format, Registry, RegistryError, Source, load

MINIMAL = {
    "id": "example_source",
    "publisher": "Example",
    "url": "https://example.com/x.xml",
    "format": "sitemap",
    "parser": "sitemap_slug",
    "licence_note": "robots.txt allows it",
}


def _write(tmp_path, *entries):
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(list(entries)), encoding="utf-8")
    return tmp_path


def _load_problems(tmp_path, *entries) -> list[str]:
    with pytest.raises(RegistryError) as excinfo:
        load(_write(tmp_path, *entries))
    return excinfo.value.problems


# --- the real registry ----------------------------------------------------

@pytest.fixture(scope="module")
def registry() -> Registry:
    return load()


def test_the_shipped_registry_is_valid(registry):
    assert len(registry) >= 5


def test_guwahati_can_never_be_displayed(registry):
    """The census reported its prices as Bengaluru ones. This is the guard."""
    assert registry["narayana_guwahati"].display_ok is False
    assert "narayana_guwahati" not in {s.id for s in registry.displayable()}


def test_the_two_narayana_units_have_different_tier_schemas(registry):
    """Which is why price_tier cannot be a shared enum across publishers."""
    blr = registry["narayana_mazumdar_shaw_bengaluru"]
    gau = registry["narayana_guwahati"]
    assert len(blr.tiers) == 11
    assert len(gau.tiers) == 8
    assert blr.tiers != gau.tiers
    # but the comparison tier is the walk-in rate in both, at index 0
    assert blr.comparison_index == gau.comparison_index == 0


def test_every_source_records_why_it_may_be_used(registry):
    for source in registry:
        assert source.licence_note.strip(), f"{source.id} has no licence note"


def test_lookup_helpers(registry):
    assert registry.for_city("bengaluru")  # case-insensitive
    assert registry.get("nope") is None
    assert "narayana_guwahati" in registry


# --- validation -----------------------------------------------------------

def test_missing_licence_note_is_rejected(tmp_path):
    problems = _load_problems(tmp_path, {**MINIMAL, "licence_note": "  "})
    assert any("licence_note" in p for p in problems)


def test_displayable_without_a_city_is_rejected(tmp_path):
    entry = {**MINIMAL, "display_ok": True, "tiers": ["OPD"], "comparison_tier": "OPD"}
    problems = _load_problems(tmp_path, entry)
    assert any("no city is set" in p for p in problems)


def test_a_pdf_must_pin_a_hash(tmp_path):
    problems = _load_problems(tmp_path, {**MINIMAL, "format": "pdf",
                                         "url": "https://example.com/x.pdf"})
    assert any("sha256" in p for p in problems)


def test_comparison_tier_must_be_one_of_the_tiers(tmp_path):
    entry = {**MINIMAL, "tiers": ["OPD", "Private"], "comparison_tier": "Walk-in"}
    problems = _load_problems(tmp_path, entry)
    assert any("is not one of its tiers" in p for p in problems)


def test_priced_source_must_name_a_comparison_tier(tmp_path):
    problems = _load_problems(tmp_path, {**MINIMAL, "tiers": ["OPD", "Private"]})
    assert any("names no comparison_tier" in p for p in problems)


def test_displayable_without_prices_is_rejected(tmp_path):
    entry = {**MINIMAL, "display_ok": True, "city": "Bengaluru"}
    problems = _load_problems(tmp_path, entry)
    assert any("carries no price tiers" in p for p in problems)


def test_http_urls_are_rejected(tmp_path):
    problems = _load_problems(tmp_path, {**MINIMAL, "url": "http://example.com/x.xml"})
    assert any("must be https" in p for p in problems)


def test_duplicate_ids_are_rejected(tmp_path):
    problems = _load_problems(tmp_path, MINIMAL, {**MINIMAL, "publisher": "Other"})
    assert any("duplicate source id" in p for p in problems)


def test_a_bad_date_is_reported_not_swallowed(tmp_path):
    problems = _load_problems(tmp_path, {**MINIMAL, "as_of": "last tuesday"})
    assert any("not an ISO date" in p for p in problems)


def test_unknown_format_is_rejected(tmp_path):
    problems = _load_problems(tmp_path, {**MINIMAL, "format": "carrier pigeon"})
    assert any("carrier pigeon" in p for p in problems)


def test_a_valid_minimal_source_loads(tmp_path):
    registry = load(_write(tmp_path, MINIMAL))
    source = registry["example_source"]
    assert source.format is Format.PDF or source.format is Format.SITEMAP
    assert not source.carries_prices
    assert source.comparison_index is None


def test_comparison_index_finds_the_walk_in_column():
    source = Source(id="s", publisher="p", url="https://x", format=Format.PDF,
                    parser="q", tiers=("A", "OPD", "B"), comparison_tier="OPD")
    assert source.comparison_index == 1
