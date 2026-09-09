"""Score the matcher against the labelled set.

Five outcomes, because "accuracy" hides the distinction that matters here:

    correct_match      matcher said X, the label says X
    wrong_match        matcher said X, the label says something else or none
    missed             matcher abstained, but there was a right answer
    correct_abstention matcher abstained and there genuinely was none
    unsure             the labeller could not decide; excluded, and reported

`wrong_match` and `missed` are not equally bad for this product. A missed row
shows the user nothing. A wrong row shows them a confident price for the wrong
test, which is the one failure the whole thing exists to avoid. So precision is
reported ahead of recall, and the headline claim should be a precision figure
at a stated coverage rather than a bare accuracy number.

Because the sample is stratified (see `sampling`), per-stratum rates are the
honest primitive. `corpus_estimate` reweights them by true stratum sizes; the
naive pooled figure over the sample is not a corpus rate and is never reported
as one.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

NONE_LABEL = "none"
UNSURE_LABEL = "unsure"

Outcome = str
OUTCOMES = ("correct_match", "wrong_match", "missed", "correct_abstention", "unsure")


@dataclass(frozen=True, slots=True)
class Judgement:
    raw_name: str
    stratum: str
    split: str
    label: str
    guess: str
    method: str
    confidence: float
    outcome: Outcome


@dataclass
class Metrics:
    judgements: list[Judgement] = field(default_factory=list)
    population: Counter[str] = field(default_factory=Counter)

    # -- counting --------------------------------------------------------
    @property
    def scored(self) -> list[Judgement]:
        """Everything the labeller could actually decide."""
        return [j for j in self.judgements if j.outcome != "unsure"]

    def counts(self, stratum: str | None = None) -> Counter[Outcome]:
        rows = self.scored if stratum is None else [
            j for j in self.scored if j.stratum == stratum
        ]
        return Counter(j.outcome for j in rows)

    # -- headline figures ------------------------------------------------
    def precision(self, stratum: str | None = None) -> float | None:
        c = self.counts(stratum)
        answered = c["correct_match"] + c["wrong_match"]
        return c["correct_match"] / answered if answered else None

    def recall(self, stratum: str | None = None) -> float | None:
        c = self.counts(stratum)
        answerable = c["correct_match"] + c["wrong_match"] + c["missed"]
        return c["correct_match"] / answerable if answerable else None

    def f1(self, stratum: str | None = None) -> float | None:
        p, r = self.precision(stratum), self.recall(stratum)
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)

    def coverage(self, stratum: str | None = None) -> float | None:
        c = self.counts(stratum)
        total = sum(c.values())
        answered = c["correct_match"] + c["wrong_match"]
        return answered / total if total else None

    def abstention_precision(self, stratum: str | None = None) -> float | None:
        """Of the times it refused, how often was refusing right?"""
        c = self.counts(stratum)
        abstained = c["missed"] + c["correct_abstention"]
        return c["correct_abstention"] / abstained if abstained else None

    # -- the number that matters -----------------------------------------
    def hard_negative_precision(self) -> float | None:
        """Accuracy on the confusable tail.

        "91% overall, 74% on the confusable tail, and here is why the tail
        fails" is a substantially stronger claim than any single accuracy
        figure, and this is that second number.
        """
        hard = [j for j in self.scored
                if j.stratum in {"declared_distinct_neighbour", "abstain_thin_margin"}]
        if not hard:
            return None
        right = sum(1 for j in hard if j.outcome in {"correct_match", "correct_abstention"})
        return right / len(hard)

    # -- reweighting -----------------------------------------------------
    def corpus_estimate(self, metric: str = "precision") -> float | None:
        """Reweight per-stratum rates by true stratum sizes.

        The sample deliberately over-draws hard strata, so pooling it directly
        would understate corpus performance. This does not fix small-sample
        noise inside a stratum - it only removes the sampling bias.
        """
        if not self.population:
            return None
        weighted, weight_used = 0.0, 0
        for stratum, size in self.population.items():
            value = getattr(self, metric)(stratum)
            if value is None:
                continue
            weighted += value * size
            weight_used += size
        return weighted / weight_used if weight_used else None

    # -- failure analysis ------------------------------------------------
    def worst(self, limit: int = 20) -> list[Judgement]:
        """Confidently wrong first. These are what the write-up explains."""
        wrong = [j for j in self.scored if j.outcome == "wrong_match"]
        return sorted(wrong, key=lambda j: -j.confidence)[:limit]

    def by_stratum(self) -> dict[str, Counter[Outcome]]:
        out: dict[str, Counter[Outcome]] = defaultdict(Counter)
        for j in self.scored:
            out[j.stratum][j.outcome] += 1
        return dict(out)


def _outcome(label: str, guess: str) -> Outcome:
    if label == UNSURE_LABEL or not label:
        return "unsure"
    if guess:
        return "correct_match" if guess == label else "wrong_match"
    return "correct_abstention" if label == NONE_LABEL else "missed"


def load_population(labels_path: Path) -> Counter[str]:
    """True stratum sizes, written beside the labels when the sample was drawn.

    Missing sidecar returns empty, and `corpus_estimate` then returns None
    rather than silently reporting a stratified rate as a corpus rate.
    """
    sidecar = labels_path.with_suffix(labels_path.suffix + ".population.json")
    if not sidecar.exists():
        return Counter()
    try:
        return Counter(json.loads(sidecar.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return Counter()


def evaluate(labels_path: Path, split: str | None = "train",
             population: Counter[str] | None = None) -> Metrics:
    """Read a labelled CSV and score it.

    `split` defaults to "train" on purpose. The holdout exists to be looked at
    once, after everything is frozen; reaching it takes an explicit argument.
    """
    judgements: list[Judgement] = []
    with labels_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if split and row.get("split") != split:
                continue
            label = (row.get("label") or "").strip()
            guess = (row.get("matcher_guess") or "").strip()
            judgements.append(Judgement(
                raw_name=row["raw_name"],
                stratum=row.get("stratum", "?"),
                split=row.get("split", "?"),
                label=label,
                guess=guess,
                method=row.get("matcher_method", "?"),
                confidence=float(row.get("matcher_confidence") or 0),
                outcome=_outcome(label, guess),
            ))
    return Metrics(judgements, population or load_population(labels_path))
