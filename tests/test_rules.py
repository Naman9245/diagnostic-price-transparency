"""The veto layer. Every case here is a confusion the census actually found."""

import pytest

from ratecard.normalise import blocks, explain
from ratecard.taxonomy import load


@pytest.fixture(scope="module")
def taxonomy():
    return load()


@pytest.mark.parametrize(
    ("left", "right", "rule"),
    [
        ("cbc", "rbc_count", "panel_vs_single"),
        ("cbc", "haemoglobin", "panel_vs_single"),
        ("lipid_profile", "lipid_profile_extended", "panel_composition"),
        ("lipid_screen", "lipid_profile", "panel_composition"),
        ("thyroid_profile", "thyroid_profile_free", "panel_composition"),
        ("albumin", "microalbumin_urine", "specimen"),
        ("urine_culture", "blood_culture", "specimen"),
        ("creatinine", "creatinine_clearance", "specimen"),
        ("xray_chest_pa", "xray_chest_pa_lateral", "views"),
        ("ct_brain_plain", "ct_brain_contrast", "contrast"),
        ("glucose_fasting", "glucose_postprandial", "declared_distinct"),
        ("glucose_fasting", "glucose_random", "declared_distinct"),
        ("clotting_time", "ct_brain_plain", "kind"),
        ("usg_abdomen", "mri_brain_plain", "modality"),
        ("troponin_i", "troponin_t", "declared_distinct"),
        ("vitamin_d_25_hydroxy", "vitamin_d_1_25_dihydroxy", "declared_distinct"),
        ("widal", "typhidot", "declared_distinct"),
        ("urea", "bun", "declared_distinct"),
        ("sgot_ast", "sgpt_alt", "declared_distinct"),
        ("ct_chest_plain", "hrct_chest", "declared_distinct"),
        ("usg_abdomen", "usg_abdomen_pelvis", "declared_distinct"),
    ],
)
def test_hard_negatives_are_blocked(taxonomy, left, right, rule):
    conflicts = explain(taxonomy[left], taxonomy[right])
    assert conflicts, f"{left} vs {right} was not blocked at all"
    assert rule in {c.rule for c in conflicts}, (
        f"{left} vs {right} blocked, but not by {rule}: {[c.rule for c in conflicts]}"
    )


def test_rules_are_symmetric(taxonomy):
    for left, right in [("cbc", "rbc_count"), ("troponin_i", "troponin_t"),
                        ("albumin", "microalbumin_urine")]:
        assert blocks(taxonomy[left], taxonomy[right])
        assert blocks(taxonomy[right], taxonomy[left])


def test_a_test_never_blocks_against_itself(taxonomy):
    for test in taxonomy:
        assert not blocks(test, test)


def test_unrelated_pairs_are_left_to_the_matcher(taxonomy):
    """The rule layer vetoes; it does not try to do the matching itself."""
    assert not blocks(taxonomy["tsh"], taxonomy["t3_total"])
    assert not blocks(taxonomy["ferritin"], taxonomy["serum_iron"])
