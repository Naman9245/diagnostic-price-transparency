"""One test per bug found in review. Each fails against the code as it was.

Kept together rather than scattered so the history of what actually went wrong
stays readable.
"""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from ratecard.evaluate.metrics import evaluate, load_population
from ratecard.evaluate.sampling import FIELDS, population_path
from ratecard.names import normalise
from ratecard.normalise.matcher import Matcher
from ratecard.taxonomy import load


@pytest.fixture(scope="module")
def taxonomy():
    return load()


@pytest.fixture(scope="module")
def matcher(taxonomy):
    return Matcher(taxonomy)


# --- bug 1: "a" was a stopword, in a domain full of single-letter identity ---

def test_single_letters_survive_normalisation():
    """"Vitamin A" collapsed to "vitamin" and "vit A" to "vit"."""
    assert normalise("Vitamin A") == "vitamin a"
    assert normalise("vit A") == "vit a"
    assert normalise("Hepatitis A") == "hepatitis a"
    assert normalise("Influenza A") == "influenza a"


def test_bare_vitamin_no_longer_resolves_to_vitamin_a(taxonomy):
    """lookup("VITAMIN") returned vitamin_a at confidence 1.0, needing no review."""
    assert taxonomy.lookup("VITAMIN") is None
    assert taxonomy.lookup("vit") is None
    assert taxonomy.lookup("vitamin a").id == "vitamin_a"
    assert taxonomy.lookup("vit a").id == "vitamin_a"


def test_stopwords_still_strip_real_noise():
    assert normalise("CBC test") == "cbc"
    assert normalise("Investigations CBC") == "cbc"


# --- bug 2: needs_review trusted any fuzzy match scoring 95+ ----------------

def test_only_exact_hits_skip_review(matcher):
    """`A or (B and C)` waved through 212 lexical guesses across the corpus,
    because WRatio emits exactly 95.0 for a common partial alignment."""
    assert not matcher.match("COMPLETE BLOOD COUNT (CBC)").needs_review

    for raw in ["BLOOD CULTURE FOR FUNGUS", "ALPHA FETO PROTEIN (AFP)",
                "BLOOD GROUP & RH TYPING", "24 HOURS URINE FOR PROTEIN"]:
        match = matcher.match(raw)
        if match.method != "exact":
            assert match.needs_review, f"{raw!r} would reach a price page unreviewed"


def test_abstentions_always_need_review(matcher):
    assert matcher.match("ACRYLIC CRANIOPLASTY").needs_review


# --- bug 3: distinct_from declarations were inert --------------------------

def test_curated_pair_resolves_when_the_name_says_which(matcher):
    """"bun" appears among bun's surfaces and nowhere in urea's."""
    assert matcher.match("blood urea nitrogen bun").test_id == "bun"
    assert matcher.match("BLOOD UREA NITROGEN (BUN)").test_id == "bun"
    assert matcher.match("CREATINE KINASE- MB (CK-MB)").test_id == "ck_mb"
    assert matcher.match("VITAMIN D 1,25 DIHYDROXY").test_id == "vitamin_d_1_25_dihydroxy"


def test_curated_pair_abstains_when_the_name_says_nothing(matcher):
    """A bare "TROPONIN" carries nothing separating troponin_i from troponin_t,
    and no amount of scoring should invent it."""
    for raw in ["TROPONIN", "troponin quantitative"]:
        match = matcher.match(raw)
        assert match.abstained, f"{raw!r} guessed {match.test_id}"
        assert match.method == "abstain_thin_margin"


def test_evidence_uses_shorter_words_than_candidate_generation(matcher):
    """"mb" is two characters and is the whole difference between CK-MB and
    total CPK; the generation-time length guard must not apply here."""
    found = matcher._distinctive_evidence("creatine kinase mb ck mb", "ck_mb", "cpk_total")
    assert found == "mb"


def test_evidence_is_directional(matcher):
    """A word distinctive to the winner is evidence; the reverse is not."""
    assert matcher._distinctive_evidence("blood urea nitrogen bun", "bun", "urea") == "bun"
    assert matcher._distinctive_evidence("blood urea", "bun", "urea") is None


# --- bug 4: corpus_estimate could never return anything --------------------

def test_population_sidecar_round_trips(tmp_path):
    """Stratum sizes were computed at sample time and thrown away, so the
    reweighting the README promises always returned None."""
    labels = tmp_path / "labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({**dict.fromkeys(FIELDS, ""), "raw_name": "a",
                         "stratum": "exact", "split": "train",
                         "matcher_guess": "cbc", "matcher_confidence": "100",
                         "label": "cbc"})
    population_path(labels).write_text('{"exact": 268, "lexical": 1512}', encoding="utf-8")

    assert load_population(labels)["exact"] == 268
    metrics = evaluate(labels, split="train")
    assert metrics.population, "population must reach Metrics"
    assert metrics.corpus_estimate("precision") is not None


def test_missing_sidecar_returns_none_rather_than_a_wrong_number(tmp_path):
    """No sidecar must mean 'no corpus estimate', never a stratified rate
    quietly reported as a corpus rate."""
    labels = tmp_path / "labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({**dict.fromkeys(FIELDS, ""), "raw_name": "a",
                         "stratum": "exact", "split": "train",
                         "matcher_guess": "cbc", "matcher_confidence": "100",
                         "label": "cbc"})
    assert load_population(labels) == {}
    assert evaluate(labels, split="train").corpus_estimate("precision") is None


def test_the_real_sample_has_its_sidecar():
    labels = Path("data/eval/labels.csv")
    if not labels.exists():
        pytest.skip("no sample drawn")
    assert population_path(labels).exists(), "sample drawn without its population"
    assert sum(load_population(labels).values()) > 0


# --- bug 7: the CLI hard-required rapidfuzz for every subcommand -----------

_BLOCK_RAPIDFUZZ = """
import sys

class _Blocker:
    def find_module(self, name, path=None):
        return self if name == "rapidfuzz" or name.startswith("rapidfuzz.") else None
    def find_spec(self, name, path=None, target=None):
        if name == "rapidfuzz" or name.startswith("rapidfuzz."):
            raise ImportError("blocked for test")
        return None

sys.meta_path.insert(0, _Blocker())
for mod in [m for m in sys.modules if m.startswith("rapidfuzz")]:
    del sys.modules[mod]

from ratecard.cli import main
raise SystemExit(main({argv!r}))
"""


def _run_without_rapidfuzz(argv: list[str]):
    """Run a CLI command in a subprocess where rapidfuzz cannot be imported."""
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_RAPIDFUZZ.format(argv=argv)],
        capture_output=True, text=True, check=False,
        cwd=Path(__file__).resolve().parent.parent,
    )


@pytest.mark.parametrize(
    "argv",
    [["validate"], ["stats"], ["lookup", "haemogram"],
     ["check", "cbc", "rbc_count"], ["hard-negatives"]],
)
def test_taxonomy_commands_run_without_rapidfuzz(argv):
    """The README promises Phase 01 runs on stdlib plus PyYAML. cli.py imported
    Matcher at module scope, so `ratecard validate` died on ModuleNotFoundError
    on any clean install."""
    result = _run_without_rapidfuzz(argv)
    assert result.returncode == 0, f"{argv} failed:\n{result.stderr[-800:]}"
    assert "rapidfuzz" not in result.stderr


def test_matcher_commands_fail_with_a_usable_message(tmp_path):
    """Commands that genuinely need it must say so, not emit a traceback."""
    result = _run_without_rapidfuzz(["match", "data/corpus/phase00.csv"])
    assert result.returncode != 0
    assert "pip install" in result.stderr
    assert "Traceback" not in result.stderr


def test_sampling_module_imports_without_rapidfuzz():
    """evaluate/sampling.py was the second eager path to rapidfuzz."""
    script = _BLOCK_RAPIDFUZZ.split("from ratecard.cli")[0] + (
        "import ratecard.evaluate.sampling as s\n"
        "assert s.STRATA\n"
        "import sys; assert 'rapidfuzz' not in sys.modules\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                            text=True, check=False,
                            cwd=Path(__file__).resolve().parent.parent)
    assert result.returncode == 0, result.stderr[-800:]
