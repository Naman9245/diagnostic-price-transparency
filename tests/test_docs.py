"""The worked-examples doc makes a claim that has to stay true.

If a teaching example leaks into the evaluation sample, reading the doc anchors
a row the same person then labels, and that row's label stops being
independent. Cheap to check, so it is checked.
"""

import csv
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parent.parent / "docs" / "labelling-worked-examples.md"
LABELS = Path(__file__).resolve().parent.parent / "data" / "eval" / "labels.csv"

# Named in the doc as a deliberate exception, and explained there.
ALLOWED_IN_SAMPLE = {"madurai"}


def _sampled_names() -> set[str]:
    with LABELS.open(newline="", encoding="utf-8") as handle:
        return {r["raw_name"].strip().lower() for r in csv.DictReader(handle)}


def _doc_examples() -> set[str]:
    """Raw names the doc discusses: `backticked` in a bold heading or a table."""
    text = DOC.read_text(encoding="utf-8")
    names: set[str] = set()
    for line in text.splitlines():
        if line.startswith(("**`", "| `")):
            match = re.search(r"`([^`]+)`", line)
            if match and " → " not in match.group(1):
                names.add(match.group(1).strip().lower())
    return names


@pytest.mark.skipif(not LABELS.exists(), reason="no sample drawn")
def test_worked_examples_do_not_leak_into_the_sample():
    leaked = (_doc_examples() & _sampled_names()) - ALLOWED_IN_SAMPLE
    assert not leaked, (
        f"worked examples that are also in the evaluation sample: {sorted(leaked)}. "
        f"Reading the doc would anchor those rows. Pick replacements from outside it."
    )


@pytest.mark.skipif(not LABELS.exists(), reason="no sample drawn")
def test_the_declared_exception_really_is_in_the_sample():
    """If madurai ever leaves the sample, the doc's carve-out is stale."""
    assert ALLOWED_IN_SAMPLE <= _sampled_names()


def test_the_doc_actually_contains_examples():
    found = _doc_examples()
    assert len(found) >= 12, f"only found {len(found)}: {sorted(found)}"
