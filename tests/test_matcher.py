"""The matcher. Every case here is drawn from the real Phase 00 corpus."""

import pytest

from ratecard.normalise.matcher import Matcher
from ratecard.taxonomy import load


@pytest.fixture(scope="module")
def matcher():
    return Matcher(load())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPLETE BLOOD COUNT (CBC)", "cbc"),
        ("SERUM CALCIUM", "calcium_serum"),
        ("TROPONIN I", "troponin_i"),
        ("X RAY CHEST PA AND LATERAL", "xray_chest_pa_lateral"),
    ],
)
def test_exact_hits_are_free_and_certain(matcher, raw, expected):
    match = matcher.match(raw)
    assert match.test_id == expected
    assert match.method == "exact"
    assert match.confidence == 100.0
    assert not match.needs_review


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # word-order variants: the whole reason token_set generates candidates
        ("lactate dehydrogenase ldh", "ldh"),
        ("blood urea nitrogen bun", "bun"),
        ("hdl cholesterol direct", "hdl_cholesterol"),
        ("total iron binding capacity tibc", "tibc"),
    ],
)
def test_word_order_variants_resolve(matcher, raw, expected):
    match = matcher.match(raw)
    assert match.test_id == expected, f"{raw!r} -> {match.test_id} ({match.reason})"
    assert match.method in {"lexical", "embedding"}


def test_urea_and_bun_do_not_collapse(matcher):
    """Both names contain 'urea'. They are separately priced tests."""
    assert matcher.match("blood urea nitrogen bun").test_id == "bun"
    assert matcher.match("blood urea").test_id == "urea"


@pytest.mark.parametrize(
    "raw",
    [
        "ACRYLIC CRANIOPLASTY",
        "TEMPORARY PACEMAKER IMPLANTATION",
        "12 GENE PANEL (NGS)",
        "ABOVE ELBOW AMPUTATION",
    ],
)
def test_things_that_are_not_diagnostics_are_refused(matcher, raw):
    """The corpus is a whole hospital catalogue. Silence is the right answer."""
    match = matcher.match(raw)
    assert match.abstained, f"{raw!r} wrongly matched {match.test_id}"
    assert match.needs_review


def test_specimen_conflict_vetoes_rather_than_guesses(matcher):
    match = matcher.match("24 HRS URINE FOR CALCIUM")
    assert match.abstained
    assert match.method == "abstain_vetoed"


def test_abstentions_always_explain_themselves(matcher):
    for raw in ["ACRYLIC CRANIOPLASTY", "24 HRS URINE FOR CALCIUM", "17 ketosteroids urine"]:
        match = matcher.match(raw)
        assert match.abstained
        assert match.reason, f"{raw!r} abstained with no reason given"


def test_generic_words_alone_are_not_grounds_for_a_candidate(matcher):
    """'12 GENE PANEL' once tied iron_studies against lipid_profile because all
    three contain the word 'panel'."""
    assert matcher.match("12 GENE PANEL (NGS)").abstained


def test_empty_and_junk_input(matcher):
    assert matcher.match("").abstained
    assert matcher.match("   ").abstained
    assert matcher.match("zzzzz qqqqq").abstained


def test_candidates_are_ranked_and_capped(matcher):
    candidates = matcher.candidates("complete blood count")
    assert candidates
    assert len(candidates) <= matcher.candidate_limit
    assert candidates == sorted(candidates, key=lambda c: -c.lexical)


def test_match_many(matcher):
    results = matcher.match_many(["CBC", "TSH", "ACRYLIC CRANIOPLASTY"])
    assert len(results) == 3
    assert [r.test_id for r in results[:2]] == ["cbc", "tsh"]
