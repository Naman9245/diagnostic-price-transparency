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
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

NONE_LABEL = "none"
UNSURE_LABEL = "unsure"

Outcome = str
OUTCOMES = ("correct_match", "wrong_match", "missed", "correct_abstention", "unsure")


# 95% two-sided. z for other levels: 1.645 (90%), 2.576 (99%).
Z_95 = 1.959964


def wilson(successes: int, total: int, z: float = Z_95) -> tuple[float, float] | None:
    """Wilson score interval for a proportion.

    Chosen over the normal approximation because the strata here are small -
    declared_distinct_neighbour has 26 rows in train - and the normal interval
    misbehaves badly at small n and at proportions near 0 or 1, where it can
    run outside [0, 1] entirely. Wilson stays inside the range and keeps
    roughly nominal coverage down to single digits.
    """
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


@dataclass(frozen=True, slots=True)
class Estimate:
    """A rate with the uncertainty that the sample size actually supports.

    A bare "94% precision" off 26 labelled rows is not a measurement, it is a
    point estimate with a interval roughly 30 points wide. Reporting the
    interval is the difference between a number that survives a follow-up
    question and one that does not.
    """

    successes: int
    total: int
    low: float | None = None
    high: float | None = None

    @property
    def value(self) -> float | None:
        return self.successes / self.total if self.total else None

    @property
    def width(self) -> float | None:
        if self.low is None or self.high is None:
            return None
        return self.high - self.low

    def labels_needed_for(self, target_width: float) -> int:
        """Roughly how many more labels would narrow the interval to `target_width`.

        Inverts the normal-approximation width, which is close enough for
        planning: n ~= 4 z^2 p(1-p) / w^2. Returns 0 when already there, and
        assumes the observed proportion holds - it will move.
        """
        p = self.value
        if p is None or target_width <= 0:
            return 0
        # Plan against a clamped proportion. An observed 100% off 8 rows has
        # p(1-p) = 0, which would claim almost no further labels are needed -
        # nonsense, since proving a high rate tightly takes *more* data, not
        # less. Clamping to [0.2, 0.8] keeps the estimate conservative while
        # still responding to where the rate actually seems to be sitting.
        clamped = min(max(p, 0.2), 0.8)
        required = math.ceil(4 * Z_95 * Z_95 * clamped * (1 - clamped) / (target_width ** 2))
        return max(0, required - self.total)

    def __str__(self) -> str:
        if self.value is None:
            return "     —"
        if self.low is None:
            return f"{100 * self.value:5.1f}%"
        return f"{100 * self.value:5.1f}%  [{100 * self.low:.0f}–{100 * self.high:.0f}]  n={self.total}"


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
    def ratio(self, metric: str, stratum: str | None = None) -> tuple[int, int]:
        """(successes, total) for a metric. The single source of truth for both
        the point estimate and its interval, so the two cannot drift apart."""
        c = self.counts(stratum)
        answered = c["correct_match"] + c["wrong_match"]
        if metric == "precision":
            return c["correct_match"], answered
        if metric == "recall":
            # Of the names that HAVE a real answer, how many were caught.
            # wrong_match covers two different failures - overreach (truth is
            # none, a test was guessed) and confusion (truth is Y, X was
            # guessed) - and only confusion belongs in this denominator. The
            # earlier `answered + missed` counted every overreach too, and on
            # the train labels reported 36.3% recall against a true 86.9%.
            rows = self.scored if stratum is None else [
                j for j in self.scored if j.stratum == stratum
            ]
            return c["correct_match"], sum(1 for j in rows if j.label != NONE_LABEL)
        if metric == "coverage":
            return answered, sum(c.values())
        if metric == "abstention_precision":
            return c["correct_abstention"], c["missed"] + c["correct_abstention"]
        if metric == "hard_negative_precision":
            hard = [j for j in self.scored
                    if j.stratum in {"declared_distinct_neighbour", "abstain_thin_margin"}]
            right = sum(1 for j in hard
                        if j.outcome in {"correct_match", "correct_abstention"})
            return right, len(hard)
        raise ValueError(f"unknown metric {metric!r}")

    def estimate(self, metric: str, stratum: str | None = None) -> Estimate:
        """A rate plus its 95% Wilson interval."""
        successes, total = self.ratio(metric, stratum)
        bounds = wilson(successes, total)
        low, high = bounds if bounds else (None, None)
        return Estimate(successes, total, low, high)

    def precision(self, stratum: str | None = None) -> float | None:
        return self.estimate("precision", stratum).value

    def recall(self, stratum: str | None = None) -> float | None:
        return self.estimate("recall", stratum).value

    def f1(self, stratum: str | None = None) -> float | None:
        p, r = self.precision(stratum), self.recall(stratum)
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)

    def coverage(self, stratum: str | None = None) -> float | None:
        return self.estimate("coverage", stratum).value

    def abstention_precision(self, stratum: str | None = None) -> float | None:
        """Of the times it refused, how often was refusing right?"""
        return self.estimate("abstention_precision", stratum).value

    # -- the number that matters -----------------------------------------
    def hard_negative_precision(self) -> float | None:
        """Accuracy on the confusable tail.

        "91% overall, 74% on the confusable tail, and here is why the tail
        fails" is a substantially stronger claim than any single accuracy
        figure, and this is that second number.
        """
        return self.estimate("hard_negative_precision").value

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
