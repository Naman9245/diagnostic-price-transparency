"""Phase 03 tooling: sampling, labelling, scoring."""

import csv

import pytest

from ratecard.evaluate.labelling import LabelSession, run, search
from ratecard.evaluate.metrics import evaluate
from ratecard.evaluate.sampling import FIELDS, build_sample, write_sample
from ratecard.taxonomy import load


@pytest.fixture(scope="module")
def taxonomy():
    return load()


@pytest.fixture
def corpus(tmp_path):
    path = tmp_path / "corpus.csv"
    rows = [("COMPLETE BLOOD COUNT (CBC)", "a"), ("haemogram", "b"), ("TSH", "a"),
            ("ACRYLIC CRANIOPLASTY", "a"), ("lactate dehydrogenase ldh", "b"),
            ("24 HRS URINE FOR CALCIUM", "a"), ("blood urea nitrogen bun", "b"),
            ("17 ketosteroids urine", "a"), ("SERUM CALCIUM", "b"), ("HBA1C", "a")]
    with path.open("w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["raw_name", "source"])
        w.writerows(rows)
    return path


def _labels_file(tmp_path, rows):
    path = tmp_path / "labels.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in FIELDS})
    return path


# --- sampling -------------------------------------------------------------

def test_sample_is_deterministic_for_a_seed(taxonomy, corpus):
    a, _ = build_sample(taxonomy, corpus, seed=7)
    b, _ = build_sample(taxonomy, corpus, seed=7)
    assert [r.raw_name for r in a] == [r.raw_name for r in b]


def test_sample_records_its_stratum_and_split(taxonomy, corpus):
    rows, _ = build_sample(taxonomy, corpus, seed=7)
    assert rows
    for row in rows:
        assert row.stratum
        assert row.split in {"train", "holdout"}


def test_population_counts_the_whole_corpus_not_the_sample(taxonomy, corpus):
    rows, population = build_sample(taxonomy, corpus, seed=7)
    assert sum(population.values()) >= len(rows)


def test_candidates_are_sorted_by_id_not_by_rank(taxonomy, corpus):
    """Anchoring guard: the labeller must not be able to read off which
    candidate the matcher preferred."""
    rows, _ = build_sample(taxonomy, corpus, seed=7)
    for row in rows:
        ids = row.candidate_ids()
        assert ids == sorted(ids)


def test_written_sample_has_an_empty_label_column(taxonomy, corpus, tmp_path):
    rows, _ = build_sample(taxonomy, corpus, seed=7)
    out = tmp_path / "labels.csv"
    write_sample(rows, out)
    with out.open(newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle))
    assert written
    assert all(r["label"] == "" for r in written)


def test_sample_file_does_not_leak_the_answer_ordering(taxonomy, corpus, tmp_path):
    """matcher_guess is stored for later scoring, but `candidates` - the only
    field the labeller is shown - must not be ordered by it."""
    rows, _ = build_sample(taxonomy, corpus, seed=7)
    out = tmp_path / "labels.csv"
    write_sample(rows, out)
    with out.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            listed = [c for c in row["candidates"].split("|") if c]
            assert listed == sorted(listed)


# --- labelling ------------------------------------------------------------

def test_session_resumes_from_the_first_unlabelled_row(tmp_path):
    path = _labels_file(tmp_path, [
        {"raw_name": "a", "label": "cbc"},
        {"raw_name": "b", "label": ""},
        {"raw_name": "c", "label": ""},
    ])
    session = LabelSession.load(path)
    assert session.done == 1
    assert session.pending() == [1, 2]


def test_every_label_is_written_immediately(tmp_path):
    """Losing an afternoon of labelling is the worst failure this tool has."""
    path = _labels_file(tmp_path, [{"raw_name": "a", "label": ""}])
    session = LabelSession.load(path, labelled_by="tester")
    session.record(0, "cbc")

    reread = LabelSession.load(path)
    assert reread.rows[0]["label"] == "cbc"
    assert reread.rows[0]["labelled_by"] == "tester"


def test_search_finds_by_id_name_and_alias(taxonomy):
    assert "cbc" in search(taxonomy, "complete blood")
    assert "cbc" in search(taxonomy, "haemogram")
    assert "hba1c" in search(taxonomy, "glycosylated")
    assert search(taxonomy, "zzzznotathing") == []


def test_run_records_choices_and_quits(taxonomy, tmp_path):
    path = _labels_file(tmp_path, [
        {"raw_name": "COMPLETE BLOOD COUNT", "stratum": "exact", "row_count": "2",
         "sources": "a", "candidates": "cbc|rbc_count", "label": ""},
        {"raw_name": "ACRYLIC CRANIOPLASTY", "stratum": "abstain_no_candidate",
         "row_count": "1", "sources": "a", "candidates": "", "label": ""},
        {"raw_name": "SOMETHING ODD", "stratum": "lexical", "row_count": "1",
         "sources": "a", "candidates": "tsh", "label": ""},
    ])
    session = LabelSession.load(path, labelled_by="tester")
    # rows are presented grouped by stratum, so the order is
    # abstain_no_candidate, exact, lexical - not file order
    answers = iter(["n", "1", "u"])
    run(session, taxonomy, read=lambda _: next(answers), write=lambda *a, **k: None)

    reread = LabelSession.load(path)
    assert [r["label"] for r in reread.rows] == ["cbc", "none", "unsure"]


def test_run_accepts_a_direct_id_and_rejects_a_bad_one(taxonomy, tmp_path):
    path = _labels_file(tmp_path, [
        {"raw_name": "x", "stratum": "lexical", "row_count": "1", "sources": "a",
         "candidates": "tsh", "label": ""},
    ])
    session = LabelSession.load(path)
    answers = iter(["=not_a_real_id", "=hba1c"])
    run(session, taxonomy, read=lambda _: next(answers), write=lambda *a, **k: None)
    assert LabelSession.load(path).rows[0]["label"] == "hba1c"


def test_skip_leaves_the_row_unlabelled(taxonomy, tmp_path):
    path = _labels_file(tmp_path, [
        {"raw_name": "x", "stratum": "lexical", "row_count": "1", "sources": "a",
         "candidates": "tsh", "label": ""},
    ])
    session = LabelSession.load(path)
    run(session, taxonomy, read=lambda _: "s", write=lambda *a, **k: None)
    assert LabelSession.load(path).rows[0]["label"] == ""


# --- metrics --------------------------------------------------------------

@pytest.fixture
def scored(tmp_path):
    return _labels_file(tmp_path, [
        # guess == label -> correct_match
        {"raw_name": "a", "stratum": "exact", "split": "train",
         "matcher_guess": "cbc", "matcher_confidence": "100", "label": "cbc"},
        # guess != label -> wrong_match, and confidently so
        {"raw_name": "b", "stratum": "lexical", "split": "train",
         "matcher_guess": "clotting_time", "matcher_confidence": "95", "label": "none"},
        # abstained but there was an answer -> missed
        {"raw_name": "c", "stratum": "abstain_low_score", "split": "train",
         "matcher_guess": "", "matcher_confidence": "0", "label": "esr"},
        # abstained and rightly -> correct_abstention
        {"raw_name": "d", "stratum": "abstain_no_candidate", "split": "train",
         "matcher_guess": "", "matcher_confidence": "0", "label": "none"},
        # hard slice, correct
        {"raw_name": "e", "stratum": "declared_distinct_neighbour", "split": "train",
         "matcher_guess": "", "matcher_confidence": "0", "label": "none"},
        # excluded
        {"raw_name": "f", "stratum": "lexical", "split": "train",
         "matcher_guess": "tsh", "matcher_confidence": "90", "label": "unsure"},
        # different split
        {"raw_name": "g", "stratum": "exact", "split": "holdout",
         "matcher_guess": "tsh", "matcher_confidence": "100", "label": "tsh"},
    ])


def test_outcomes_are_classified(scored):
    m = evaluate(scored, split="train")
    counts = m.counts()
    assert counts["correct_match"] == 1
    assert counts["wrong_match"] == 1
    assert counts["missed"] == 1
    assert counts["correct_abstention"] == 2


def test_unsure_is_excluded_but_visible(scored):
    m = evaluate(scored, split="train")
    assert len(m.judgements) == 6
    assert len(m.scored) == 5


def test_split_filter(scored):
    assert len(evaluate(scored, split="holdout").scored) == 1
    assert len(evaluate(scored, split=None).scored) == 6


def test_precision_recall_and_coverage(scored):
    m = evaluate(scored, split="train")
    assert m.precision() == pytest.approx(1 / 2)
    # Two names have a real answer (a: cbc, c: esr) and one was caught. This
    # asserted 1/3 until 2026-09-23, which enshrined a bug: row b is an
    # overreach (truth none) and does not belong in recall's denominator.
    assert m.recall() == pytest.approx(1 / 2)
    assert m.coverage() == pytest.approx(2 / 5)
    assert m.abstention_precision() == pytest.approx(2 / 3)


def test_hard_negative_accuracy_uses_only_the_hard_strata(scored):
    m = evaluate(scored, split="train")
    assert m.hard_negative_precision() == pytest.approx(1.0)


def test_worst_lists_confidently_wrong_first(scored):
    worst = evaluate(scored, split="train").worst()
    assert [j.raw_name for j in worst] == ["b"]
    assert worst[0].confidence == 95.0


def test_empty_metrics_return_none_not_zero():
    from collections import Counter

    from ratecard.evaluate.metrics import Metrics
    m = Metrics([], Counter())
    assert m.precision() is None
    assert m.f1() is None
    assert m.hard_negative_precision() is None


def test_rows_are_presented_grouped_by_stratum(taxonomy, tmp_path):
    """Staying in one decision mode is much faster than switching every row."""
    path = _labels_file(tmp_path, [
        {"raw_name": "a", "stratum": "lexical", "candidates": "tsh", "label": ""},
        {"raw_name": "b", "stratum": "exact", "candidates": "cbc", "label": ""},
        {"raw_name": "c", "stratum": "lexical", "candidates": "esr", "label": ""},
    ])
    session = LabelSession.load(path)
    shown: list[str] = []

    def read(_):
        return "n"

    def write(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        for name in ("a", "b", "c"):
            if f"\n    {name}\n" in text:
                shown.append(name)

    run(session, taxonomy, read=read, write=write)
    assert shown == ["b", "a", "c"], f"expected exact first, got {shown}"


def test_undo_restores_the_previous_row(taxonomy, tmp_path):
    """Without this, a misclick meant living with it or restarting."""
    path = _labels_file(tmp_path, [
        {"raw_name": "a", "stratum": "lexical", "candidates": "tsh|esr", "label": ""},
        {"raw_name": "b", "stratum": "lexical", "candidates": "cbc", "label": ""},
    ])
    session = LabelSession.load(path)
    answers = iter(["1", "z", "2", "1"])
    run(session, taxonomy, read=lambda _: next(answers), write=lambda *a, **k: None)

    reread = LabelSession.load(path)
    assert reread.rows[0]["label"] == "esr", "undo then re-pick should land on the 2nd option"
    assert reread.rows[1]["label"] == "cbc"


def test_undo_with_nothing_to_undo_is_harmless(taxonomy, tmp_path):
    path = _labels_file(tmp_path, [
        {"raw_name": "a", "stratum": "lexical", "candidates": "tsh", "label": ""},
    ])
    session = LabelSession.load(path)
    answers = iter(["z", "1"])
    run(session, taxonomy, read=lambda _: next(answers), write=lambda *a, **k: None)
    assert LabelSession.load(path).rows[0]["label"] == "tsh"


def test_dot_repeats_the_previous_label(taxonomy, tmp_path):
    """Runs of near-identical rows are common - 'USG left/right inguinal region'."""
    path = _labels_file(tmp_path, [
        {"raw_name": "a", "stratum": "abstain_no_candidate", "candidates": "", "label": ""},
        {"raw_name": "b", "stratum": "abstain_no_candidate", "candidates": "", "label": ""},
        {"raw_name": "c", "stratum": "abstain_no_candidate", "candidates": "", "label": ""},
    ])
    session = LabelSession.load(path)
    answers = iter(["n", ".", "."])
    run(session, taxonomy, read=lambda _: next(answers), write=lambda *a, **k: None)
    assert [r["label"] for r in LabelSession.load(path).rows] == ["none", "none", "none"]


def test_dot_before_any_label_is_rejected(taxonomy, tmp_path):
    path = _labels_file(tmp_path, [
        {"raw_name": "a", "stratum": "lexical", "candidates": "tsh", "label": ""},
    ])
    session = LabelSession.load(path)
    answers = iter([".", "1"])
    run(session, taxonomy, read=lambda _: next(answers), write=lambda *a, **k: None)
    assert LabelSession.load(path).rows[0]["label"] == "tsh"


# --- confidence intervals -------------------------------------------------

def test_wilson_stays_inside_zero_and_one():
    """The normal approximation runs outside [0,1] at extreme proportions,
    which is why these strata use Wilson instead."""
    from ratecard.evaluate.metrics import wilson

    for successes, total in [(0, 10), (10, 10), (1, 3), (26, 26), (0, 1)]:
        low, high = wilson(successes, total)
        assert 0.0 <= low <= high <= 1.0


def test_wilson_needs_a_sample():
    from ratecard.evaluate.metrics import wilson

    assert wilson(0, 0) is None


def test_interval_narrows_as_n_grows():
    from ratecard.evaluate.metrics import wilson

    widths = []
    for n in (10, 50, 200, 1000):
        low, high = wilson(round(0.9 * n), n)
        widths.append(high - low)
    assert widths == sorted(widths, reverse=True)


def test_estimate_reports_n_and_width(scored):
    m = evaluate(scored, split="train")
    estimate = m.estimate("precision")
    assert estimate.total == 2
    assert estimate.value == pytest.approx(0.5)
    assert estimate.width > 0.5, "two rows cannot support a narrow interval"


def test_point_estimate_and_interval_cannot_disagree(scored):
    """Both derive from ratio(), deliberately - they used to be counted twice."""
    m = evaluate(scored, split="train")
    for metric in ("precision", "recall", "coverage", "abstention_precision",
                   "hard_negative_precision"):
        successes, total = m.ratio(metric)
        estimate = m.estimate(metric)
        assert (estimate.successes, estimate.total) == (successes, total)
        if total:
            assert estimate.low <= estimate.value <= estimate.high


def test_ratio_rejects_an_unknown_metric(scored):
    with pytest.raises(ValueError, match="unknown metric"):
        evaluate(scored, split="train").ratio("nonsense")


def test_sample_size_planning_is_conservative_at_extremes():
    """An observed 100% has p(1-p)=0, which would claim no more labels are
    needed. Proving a high rate tightly takes more data, not less."""
    from ratecard.evaluate.metrics import Estimate, wilson

    low, high = wilson(8, 8)
    perfect = Estimate(8, 8, low, high)
    assert perfect.labels_needed_for(0.10) > 100

    low, high = wilson(50, 100)
    middling = Estimate(50, 100, low, high)
    assert middling.labels_needed_for(0.10) > 0


def test_no_more_labels_needed_once_wide_enough():
    from ratecard.evaluate.metrics import Estimate, wilson

    low, high = wilson(900, 1000)
    assert Estimate(900, 1000, low, high).labels_needed_for(0.50) == 0


def test_estimate_renders_with_and_without_an_interval():
    from ratecard.evaluate.metrics import Estimate

    assert str(Estimate(0, 0)) == "     —"
    assert "n=26" in str(Estimate(24, 26, 0.76, 0.98))
