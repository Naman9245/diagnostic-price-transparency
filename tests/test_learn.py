"""The learned acceptor: features, persistence, training and the matcher hook."""

import json
from pathlib import Path

import pytest

from ratecard.learn.features import FEATURE_NAMES, Featuriser
from ratecard.learn.model import Acceptor, name_decisions, rates, score
from ratecard.normalise.matcher import Matcher
from ratecard.taxonomy import load

MODEL = Path(__file__).resolve().parent.parent / "data" / "models" / "acceptor.json"


@pytest.fixture(scope="module")
def taxonomy():
    return load()


@pytest.fixture(scope="module")
def featuriser(taxonomy):
    return Featuriser(taxonomy)


def _ranked(taxonomy, raw):
    return sorted(Matcher(taxonomy).candidates(raw), key=lambda c: -c.score)


# --- features ---------------------------------------------------------------

def test_one_value_per_declared_feature(taxonomy, featuriser):
    ranked = _ranked(taxonomy, "SERUM CALCIUM")
    assert len(featuriser.pair("SERUM CALCIUM", ranked[0], ranked)) == len(FEATURE_NAMES)


def test_vocabulary_is_built_from_the_taxonomy_not_a_list(featuriser):
    assert "hemoglobin" in featuriser.vocabulary
    assert "viral" not in featuriser.vocabulary
    assert len(featuriser.vocabulary) > 400


def test_out_of_vocabulary_words_are_what_flag_overreach(taxonomy, featuriser):
    """The error analysis found every overreach carries words the taxonomy
    never uses. That is the signal these features exist to carry."""
    oov = FEATURE_NAMES.index("oov_frac")
    for raw in ["hiv 1 viral load", "t3 reverse"]:
        ranked = _ranked(taxonomy, raw)
        assert featuriser.pair(raw, ranked[0], ranked)[oov] > 0.4, raw
    ranked = _ranked(taxonomy, "SERUM CALCIUM")
    assert featuriser.pair("SERUM CALCIUM", ranked[0], ranked)[oov] == 0.0


def test_is_top_marks_only_the_leader(taxonomy, featuriser):
    ranked = _ranked(taxonomy, "troponin quantitative")
    idx = FEATURE_NAMES.index("is_top")
    flags = [featuriser.pair("troponin quantitative", c, ranked)[idx] for c in ranked]
    assert flags[0] == 1.0 and sum(flags) == 1.0


# --- scoring logic ----------------------------------------------------------

def test_overreach_and_confusion_are_counted_separately():
    truth = {"a": "cbc", "b": "none", "c": "troponin_t", "d": "hba1c", "e": "none"}
    decisions = {"a": "cbc", "b": "tsh", "c": "troponin_i", "d": "", "e": ""}
    c = score(decisions, truth)
    assert c == {"correct_match": 1, "overreach": 1, "confusion": 1,
                 "missed": 1, "correct_abstention": 1}


def test_recall_ignores_overreach():
    r = rates({"correct_match": 1, "overreach": 50, "confusion": 0,
               "missed": 1, "correct_abstention": 0})
    assert r["recall"] == pytest.approx(0.5)
    assert r["precision"] == pytest.approx(1 / 51)


def test_name_decision_takes_the_best_candidate_above_threshold():
    names = ["x", "x", "y", "y"]
    probs = [0.95, 0.40, 0.30, 0.20]
    cids = ["cbc", "rbc_count", "tsh", "t3_total"]
    assert name_decisions(names, probs, cids, 0.9) == {"x": "cbc", "y": ""}


# --- persistence ------------------------------------------------------------

def _toy(threshold=0.5):
    n = len(FEATURE_NAMES)
    return Acceptor(FEATURE_NAMES, [0.0] * n, [1.0] * n, [0.0] * n, 0.0, threshold)


def test_round_trips_through_json(tmp_path):
    original = _toy(0.7)
    path = tmp_path / "m.json"
    original.save(path)
    loaded = Acceptor.load(path)
    assert loaded.threshold == 0.7
    assert loaded.feature_names == FEATURE_NAMES


def test_refuses_a_model_trained_on_other_features(tmp_path):
    """Scoring with mismatched columns would silently produce nonsense."""
    path = tmp_path / "m.json"
    payload = json.loads(_toy().to_json())
    payload["feature_names"] = list(reversed(payload["feature_names"]))
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="different feature set"):
        Acceptor.load(path)


def test_inference_needs_no_scikit_learn():
    """Pure arithmetic: an all-zero model is a coin flip."""
    assert _toy().probability([1.0] * len(FEATURE_NAMES)) == pytest.approx(0.5)


# --- the shipped model, if trained ------------------------------------------

@pytest.mark.skipif(not MODEL.exists(), reason="no trained model")
def test_shipped_model_refuses_the_overreach_cases(taxonomy):
    matcher = Matcher(taxonomy, acceptor=Acceptor.load(MODEL))
    for raw in ["hiv 1 viral load", "t3 reverse", "CT ELBOW LEFT", "albumin fluid"]:
        assert matcher.match(raw).abstained, raw


@pytest.mark.skipif(not MODEL.exists(), reason="no trained model")
def test_shipped_model_keeps_the_exact_layer_and_the_veto(taxonomy):
    matcher = Matcher(taxonomy, acceptor=Acceptor.load(MODEL))
    exact = matcher.match("COMPLETE BLOOD COUNT (CBC)")
    assert exact.method == "exact" and exact.test_id == "cbc"
    assert matcher.match("24 HRS URINE FOR CALCIUM").method == "abstain_vetoed"


@pytest.mark.skipif(not MODEL.exists(), reason="no trained model")
def test_learned_matches_still_need_review(taxonomy):
    """A better model does not earn skip-review; only exact hits do."""
    matcher = Matcher(taxonomy, acceptor=Acceptor.load(MODEL))
    m = matcher.match("lactate dehydrogenase ldh")
    if m.test_id:
        assert m.method == "learned"
        assert m.needs_review


@pytest.mark.skipif(not MODEL.exists(), reason="no trained model")
def test_shipped_model_records_its_provenance():
    meta = Acceptor.load(MODEL).metadata
    for key in ("trained", "positives", "cv_precision", "cv_recall", "labels"):
        assert key in meta
