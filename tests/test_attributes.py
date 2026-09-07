"""Attributes read out of a raw name must be hints, never guesses."""

import pytest

from ratecard.normalise.attributes import Attributes, attributes_of, extract, vetoes
from ratecard.taxonomy import load
from ratecard.taxonomy.schema import Modality, Specimen


@pytest.fixture(scope="module")
def taxonomy():
    return load()


@pytest.mark.parametrize(
    ("raw", "field", "expected"),
    [
        ("CT BRAIN PLAIN", "contrast", False),
        ("CECT ABDOMEN AND PELVIS", "contrast", True),
        ("MRI BRAIN WITH CONTRAST", "contrast", True),
        ("HRCT CHEST", "contrast", False),
        ("24 HRS URINE FOR CALCIUM", "specimen", Specimen.URINE_24H),
        ("URINE ROUTINE", "specimen", Specimen.URINE),
        ("SERUM CALCIUM", "specimen", Specimen.SERUM),
        ("STOOL OCCULT BLOOD", "specimen", Specimen.STOOL),
        ("FREE T3", "qualifier", "free"),
        ("TOTAL T3", "qualifier", "total"),
        ("SUGAR PP", "fasting", "postprandial"),
        ("FBS", "fasting", "fasting"),
        ("RBS", "fasting", "random"),
        ("X RAY CHEST PA AND LATERAL", "views", 2),
        ("X RAY CHEST PA VIEW", "views", 1),
        ("USG ABDOMEN", "modality", Modality.ULTRASOUND),
        ("MRI KNEE", "modality", Modality.MRI),
    ],
)
def test_extract(raw, field, expected):
    assert getattr(extract(raw), field) == expected


def test_ct_needs_a_region_before_it_means_a_scan():
    """"CT" is how every Indian rate card abbreviates Clotting Time."""
    assert extract("CLOTTING TIME (CT)").modality is None
    assert extract("CT BRAIN").modality is Modality.CT


def test_absent_attribute_is_unknown_not_false():
    attrs = extract("HAEMOGLOBIN")
    assert attrs.contrast is None
    assert attrs.views is None
    assert attrs.qualifier is None


def test_empty_name_yields_empty_attributes():
    assert extract("").is_empty()
    assert Attributes().is_empty()


def test_declared_fields_win_over_the_name(taxonomy):
    """The taxonomy declares specimen outright; the name need not repeat it."""
    assert attributes_of(taxonomy["haemoglobin"]).specimen is Specimen.WHOLE_BLOOD


def test_qualifier_comes_from_the_canonical_name(taxonomy):
    """There is no `qualifier` field - free vs total is read from the name,
    which is what lets Free T3 be vetoed against Total T3 for free."""
    assert attributes_of(taxonomy["t3_free"]).qualifier == "free"
    assert attributes_of(taxonomy["t3_total"]).qualifier == "total"


@pytest.mark.parametrize(
    ("raw", "test_id"),
    [
        ("CT BRAIN PLAIN", "ct_brain_contrast"),
        ("CECT BRAIN", "ct_brain_plain"),
        ("24 HRS URINE FOR CALCIUM", "calcium_serum"),
        ("FREE T3", "t3_total"),
        ("TOTAL T3", "t3_free"),
        ("X RAY CHEST PA AND LATERAL", "xray_chest_pa"),
        ("SUGAR PP", "glucose_fasting"),
        ("URINE MICROALBUMIN", "albumin"),
    ],
)
def test_raw_name_vetoes_the_wrong_candidate(taxonomy, raw, test_id):
    assert vetoes(raw, taxonomy[test_id])


@pytest.mark.parametrize(
    ("raw", "test_id"),
    [
        ("CT BRAIN PLAIN", "ct_brain_plain"),
        ("FREE T3", "t3_free"),
        ("SUGAR PP", "glucose_postprandial"),
        ("COMPLETE BLOOD COUNT", "cbc"),
        ("CLOTTING TIME (CT)", "clotting_time"),
    ],
)
def test_the_right_candidate_is_not_vetoed(taxonomy, raw, test_id):
    assert not vetoes(raw, taxonomy[test_id])
