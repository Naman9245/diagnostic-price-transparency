"""Train, cross-validate, persist and apply the learned acceptor.

Logistic regression, deliberately. There are 345 labelled rows and about 60
positives; anything with more capacity memorises them and reports numbers that
do not survive new data. A linear model over a handful of meaningful features
generalises from little, and its coefficients say *why* it rejects a match -
which is the part worth putting in front of anyone reading the evaluation.

Training needs scikit-learn. Inference does not: the fitted model is saved as
JSON (feature names, scaling, coefficients, threshold) and scored with plain
arithmetic, so matching keeps working on an install without the learn extra -
the same rule every other optional dependency here follows.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ratecard.learn.features import FEATURE_NAMES

DEFAULT_PATH = Path("data/models/acceptor.json")
# The operating point is chosen for precision, because a wrong price shown
# confidently is the failure this project exists to prevent.
#
# 0.80 rather than 0.90, on the evidence. On the train labels the two targets
# realise 87.5% [64-97] and 90.0% [60-98] precision - intervals that overlap
# almost entirely at 19 positives - while recall is 73.7% against 47.4%. The
# higher target buys one fewer error for nearly half the recall. Revisit on the
# holdout; with this few positives the threshold is the least stable number here.
TARGET_PRECISION = 0.80


@dataclass
class Acceptor:
    feature_names: tuple[str, ...]
    mean: list[float]
    scale: list[float]
    coef: list[float]
    intercept: float
    threshold: float
    metadata: dict = field(default_factory=dict)

    def probability(self, features: list[float]) -> float:
        z = self.intercept
        for x, mu, sd, w in zip(features, self.mean, self.scale, self.coef, strict=True):
            z += w * ((x - mu) / sd if sd else 0.0)
        return 1.0 / (1.0 + math.exp(-z))

    def accept(self, features: list[float]) -> bool:
        return self.probability(features) >= self.threshold

    # -- persistence -------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({
            "feature_names": list(self.feature_names),
            "mean": self.mean, "scale": self.scale,
            "coef": self.coef, "intercept": self.intercept,
            "threshold": self.threshold, "metadata": self.metadata,
        }, indent=2)

    def save(self, path: Path = DEFAULT_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> Acceptor:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if tuple(payload["feature_names"]) != FEATURE_NAMES:
            raise ValueError(
                f"{path} was trained on a different feature set. Retrain with "
                f"`ratecard train` rather than scoring with mismatched columns."
            )
        return cls(tuple(payload["feature_names"]), payload["mean"], payload["scale"],
                   payload["coef"], payload["intercept"], payload["threshold"],
                   payload.get("metadata", {}))

    def explain(self) -> list[tuple[str, float]]:
        """Standardised coefficients, largest effect first."""
        return sorted(zip(self.feature_names, self.coef, strict=True),
                      key=lambda kv: -abs(kv[1]))


# -- training ----------------------------------------------------------------

def _fit(X, y, w, C: float):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler().fit(X)
    model = LogisticRegression(C=C, class_weight="balanced", max_iter=2000)
    model.fit(scaler.transform(X), y, sample_weight=w)
    return scaler, model


def name_decisions(names, probs, candidate_ids, threshold: float) -> dict[str, str]:
    """Per raw name: the best candidate if it clears the threshold, else abstain."""
    best: dict[str, tuple[float, str]] = {}
    for name, p, cid in zip(names, probs, candidate_ids, strict=True):
        if name not in best or p > best[name][0]:
            best[name] = (p, cid)
    return {n: (cid if p >= threshold else "") for n, (p, cid) in best.items()}


def score(decisions: dict[str, str], truth: dict[str, str]) -> dict[str, int]:
    """Outcome counts over every labelled name, deciding or not.

    `overreach` and `confusion` are kept apart because they mean different
    things and recall must only count the second: an overreach is a name with
    no right answer that got one anyway, a confusion is a name whose right
    answer was passed over for a wrong one.
    """
    counts = {"correct_match": 0, "overreach": 0, "confusion": 0,
              "missed": 0, "correct_abstention": 0}
    for name, label in truth.items():
        guess = decisions.get(name, "")
        if guess:
            if guess == label:
                counts["correct_match"] += 1
            else:
                counts["overreach" if label == "none" else "confusion"] += 1
        else:
            counts["correct_abstention" if label == "none" else "missed"] += 1
    return counts


def rates(counts: dict[str, int]) -> dict[str, float | int]:
    wrong = counts["overreach"] + counts["confusion"]
    answered = counts["correct_match"] + wrong
    answerable = counts["correct_match"] + counts["confusion"] + counts["missed"]
    return {
        "answered": answered, "answerable": answerable, "wrong": wrong,
        "precision": counts["correct_match"] / answered if answered else float("nan"),
        "recall": counts["correct_match"] / answerable if answerable else float("nan"),
    }


def cross_validate(pairs, folds: int = 5, C: float = 1.0, seed: int = 20260923):
    """Out-of-fold probabilities, grouped by raw name so no name leaks."""
    import numpy as np
    from sklearn.model_selection import GroupKFold

    X = np.asarray(pairs.X); y = np.asarray(pairs.y); w = np.asarray(pairs.weights)
    groups = np.asarray(pairs.groups)
    oof = np.zeros(len(y))
    splitter = GroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train_idx, test_idx in splitter.split(X, y, groups):
        scaler, model = _fit(X[train_idx], y[train_idx], w[train_idx], C)
        oof[test_idx] = model.predict_proba(scaler.transform(X[test_idx]))[:, 1]
    return oof.tolist()


def choose_threshold(pairs, probs, target: float = TARGET_PRECISION) -> tuple[float, dict]:
    """Lowest threshold (most coverage) whose out-of-fold precision meets target."""
    grid = sorted({round(p, 4) for p in probs}, reverse=True)
    chosen, chosen_counts = 1.0, None
    for t in grid:
        counts = score(name_decisions(pairs.groups, probs, pairs.candidate_ids, t), pairs.truth)
        r = rates(counts)
        if r["answered"] and r["precision"] >= target:
            chosen, chosen_counts = t, counts
    if chosen_counts is None:
        chosen_counts = score({}, pairs.truth)
    return chosen, chosen_counts


def train(pairs, threshold: float, C: float = 1.0, metadata: dict | None = None) -> Acceptor:
    """Fit on every pair and wrap the result for pure-Python inference."""
    import numpy as np

    scaler, model = _fit(np.asarray(pairs.X), np.asarray(pairs.y),
                         np.asarray(pairs.weights), C)
    meta = {"trained": datetime.now(UTC).isoformat(timespec="seconds"),
            "pairs": len(pairs.y), "positives": int(sum(pairs.y)),
            "names": len(pairs.truth), "C": C, **(metadata or {})}
    return Acceptor(FEATURE_NAMES, scaler.mean_.tolist(), scaler.scale_.tolist(),
                    model.coef_[0].tolist(), float(model.intercept_[0]), threshold, meta)
