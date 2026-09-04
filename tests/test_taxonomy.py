"""The taxonomy is hand-written, so its invariants are the only safety net."""

import pytest

from ratecard.names import alias_key
from ratecard.taxonomy import load
from ratecard.taxonomy.schema import Kind


@pytest.fixture(scope="module")
def taxonomy():
    return load()


def test_taxonomy_loads_and_validates(taxonomy):
    assert len(taxonomy) > 150, "Phase 01 targets roughly 150 canonical tests"


def test_every_alias_resolves_to_its_own_test(taxonomy):
    for test in taxonomy:
        for alias in test.aliases:
            assert taxonomy.lookup(alias) is test, f"{alias!r} did not resolve to {test.id}"


def test_no_alias_is_claimed_by_two_tests(taxonomy):
    """The load-bearing invariant. A collision means the matcher can be handed
    a name with no correct answer available and will still return one."""
    seen: dict[str, str] = {}
    for test in taxonomy:
        for surface in (test.name, *test.aliases):
            key = alias_key(surface)
            assert seen.setdefault(key, test.id) == test.id, f"collision on {key!r}"


def test_panels_declare_their_analytes(taxonomy):
    for test in taxonomy:
        assert test.is_panel == bool(test.analytes)


def test_components_are_canonical_ids(taxonomy):
    for test in taxonomy:
        for component in test.components:
            assert component in taxonomy


def test_lab_tests_carry_a_specimen(taxonomy):
    for test in taxonomy:
        if test.kind is Kind.LAB:
            assert test.specimen is not None


def test_imaging_studies_carry_a_modality_and_no_specimen(taxonomy):
    for test in taxonomy:
        if test.kind is Kind.IMAGING:
            assert test.modality is not None
            assert test.specimen is None


def test_distinct_from_references_resolve(taxonomy):
    for test in taxonomy:
        for other in test.distinct_from:
            assert other in taxonomy
            assert other != test.id


@pytest.mark.parametrize(
    ("raw", "expected_id"),
    [
        ("COMPLETE BLOOD COUNT (CBC)", "cbc"),
        ("haemogram", "cbc"),
        ("CBP", "cbc"),
        ("LIPID PROFILE (CHOL TRIG)", "lipid_profile"),
        ("Sugar F", "glucose_fasting"),
        ("PPBS", "glucose_postprandial"),
        ("KFT", "kft"),
        ("RFT", "kft"),
        ("urine R/M", "urine_routine"),
        ("CUE", "urine_routine"),
        ("2D echo", "echocardiography"),
        ("USG whole abdomen", "usg_abdomen"),
        ("HbA1c", "hba1c"),
        ("vit D", "vitamin_d_25_hydroxy"),
    ],
)
def test_real_source_spellings_resolve(taxonomy, raw, expected_id):
    """Names taken from how the confirmed sources actually write them."""
    resolved = taxonomy.lookup(raw)
    assert resolved is not None, f"{raw!r} did not resolve at all"
    assert resolved.id == expected_id


def test_unknown_name_returns_none(taxonomy):
    assert taxonomy.lookup("zzz not a real test zzz") is None
