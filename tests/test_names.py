"""The normaliser must remove noise without ever removing a distinction."""

import pytest

from ratecard.names import alias_key, normalise, tokens


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPLETE BLOOD COUNT (CBC)", "complete blood count cbc"),
        ("  Lipid   Profile  ", "lipid profile"),
        ("T3/T4/TSH", "t3 t4 tsh"),
        ("URINE ROUTINE & MICROSCOPY", "urine routine microscopy"),
        ("Haemoglobin", "hemoglobin"),
        ("Haemogram", "hemogram"),
        ("Vitamin D 25-Hydroxy", "vitamin d 25 hydroxy"),
        ("CBC test", "cbc"),
        ("Serum Calcium - Rs 350", "serum calcium"),
        ("Lipid Profile ₹2,110", "lipid profile"),
        ("", ""),
    ],
)
def test_normalise(raw, expected):
    assert normalise(raw) == expected


def test_normalise_is_idempotent():
    for raw in ["COMPLETE BLOOD COUNT (CBC)", "Haemoglobin", "T3/T4/TSH"]:
        once = normalise(raw)
        assert normalise(once) == once


def test_normalisation_never_merges_the_vitamin_d_pair():
    """The census's headline confusable pair. Priced Rs 2,890 and Rs 2,800."""
    assert normalise("VITAMIN D 25 HYDROXY") != normalise("VITAMIN D 1 25 DIHYDROXY")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("CBC", "RBC"),
        ("Lipid Profile", "Lipid Profile Extended"),
        ("Troponin I", "Troponin T"),
        ("SGOT", "SGPT"),
        ("Free T3", "Total T3"),
        ("CT Brain Plain", "CT Brain with Contrast"),
    ],
)
def test_normalisation_preserves_hard_negative_distinctions(left, right):
    assert normalise(left) != normalise(right)


def test_alias_key_matches_normalise():
    assert alias_key("Complete Blood Count") == normalise("Complete Blood Count")


def test_tokens_are_a_set():
    assert tokens("Complete Blood Count (CBC)") == frozenset(
        {"complete", "blood", "count", "cbc"}
    )
