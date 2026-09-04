"""Coverage reporting, exercised on a synthetic corpus.

The real Phase 00 corpus is not on disk, so these fixtures stand in for it.
They are shaped like the real dump: raw_name, source, price, tier.
"""

import csv

import pytest

from ratecard.taxonomy import load
from ratecard.taxonomy.coverage import analyse, hard_negative_pairs

ROWS = [
    # resolve exactly, via aliases
    ("COMPLETE BLOOD COUNT (CBC)", "narayana", "600", "OPD"),
    ("Haemogram", "redcliffe", "349", "walkin"),
    ("CBC", "lalpath", "300", "walkin"),
    ("LIPID PROFILE (CHOL TRIG)", "narayana", "2110", "OPD"),
    ("TSH", "narayana", "860", "OPD"),
    ("HBA1C", "narayana", "1050", "OPD"),
    ("URINE ROUTINE & MICROSCOPY", "narayana", "290", "OPD"),
    ("Sugar F", "redcliffe", "80", "walkin"),
    # reachable by containment but not exact
    ("SERUM TSH LEVEL ESTIMATION", "narayana", "900", "OPD"),
    # genuinely uncovered - these are the curation worklist
    ("ACRYLIC CRANIOPLASTY", "narayana", "45000", "OPD"),
    ("TEMPORARY PACEMAKER IMPLANTATION", "narayana", "18000", "OPD"),
    ("ACRYLIC CRANIOPLASTY", "narayana", "45000", "General"),
]


@pytest.fixture(scope="module")
def taxonomy():
    return load()


@pytest.fixture
def corpus(tmp_path):
    path = tmp_path / "phase00.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["raw_name", "source", "price", "tier"])
        writer.writerows(ROWS)
    return path


def test_counts_rows_and_distinct_names(taxonomy, corpus):
    report = analyse(taxonomy, corpus)
    assert report.rows == len(ROWS)
    assert report.distinct_names == len({row[0] for row in ROWS})


def test_exact_coverage_counts_only_alias_hits(taxonomy, corpus):
    report = analyse(taxonomy, corpus)
    assert report.exact_rows == 8
    assert 0 < report.exact_pct < 100


def test_reachable_is_a_ceiling_above_exact(taxonomy, corpus):
    report = analyse(taxonomy, corpus)
    assert report.reachable_rows >= report.exact_rows


def test_unmatched_is_ranked_by_frequency_and_is_the_worklist(taxonomy, corpus):
    report = analyse(taxonomy, corpus)
    names = [name for name, _ in report.unmatched]
    assert "ACRYLIC CRANIOPLASTY" in names
    assert "TEMPORARY PACEMAKER IMPLANTATION" in names
    # the duplicated row must sort first on count
    assert report.unmatched[0] == ("ACRYLIC CRANIOPLASTY", 2)


def test_per_source_breakdown(taxonomy, corpus):
    report = analyse(taxonomy, corpus)
    assert set(report.per_source) == {"narayana", "redcliffe", "lalpath"}


def test_missing_name_column_is_an_error(taxonomy, tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("price,tier\n600,OPD\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no recognised name column"):
        analyse(taxonomy, path)


def test_hard_negative_pairs_are_seeded_from_declarations(taxonomy):
    pairs = hard_negative_pairs(taxonomy)
    assert len(pairs) >= 25
    flat = {(a, b) for a, b, _ in pairs}
    assert ("troponin_i", "troponin_t") in flat
    assert ("vitamin_d_25_hydroxy", "vitamin_d_1_25_dihydroxy") in flat
    # each pair appears once, not once per direction
    assert len(flat) == len(pairs)
