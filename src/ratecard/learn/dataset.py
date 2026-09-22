"""Turn the labelled evaluation set into pairwise training examples.

One example per (raw name, surviving candidate). The label is 1 when that
candidate is the one the labeller chose, 0 otherwise - so a raw name whose
truth is "none" contributes only negatives, which is exactly how the model
learns not to overreach.

Two exclusions, both deliberate:

  - rows labelled `unsure` carry no truth to learn from
  - exact alias hits are dropped. At inference they bypass the model entirely
    (they are 100% precise on the train labels), so training on them would
    teach the model about a distribution it never has to decide.

Vetoed candidates are dropped before featurising. The veto is a hard rule and
stays one; the model chooses only among what the rules already allow.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ratecard.learn.features import Featuriser
from ratecard.normalise.attributes import extract
from ratecard.normalise.matcher import Matcher
from ratecard.taxonomy.loader import Taxonomy


@dataclass
class PairSet:
    X: list[list[float]]
    y: list[int]
    groups: list[str]          # raw name - pairs from one name never straddle folds
    weights: list[float]       # corpus reweighting by stratum
    candidate_ids: list[str]
    truth: dict[str, str]      # raw name -> labelled answer
    baseline: dict[str, str]   # raw name -> what the rule-based matcher said ("" = abstain)
    strata: dict[str, str]


def survivors(matcher: Matcher, raw_name: str) -> list:
    """Candidates the hard rules allow, ranked - the model's decision space."""
    found = matcher.candidates(raw_name)
    if not found:
        return []
    found = matcher._apply_vetoes(extract(raw_name), found)
    return sorted((c for c in found if not c.blocked), key=lambda c: -c.score)


def build(taxonomy: Taxonomy, labels_path: Path, split: str = "train") -> PairSet:
    matcher = Matcher(taxonomy)
    featuriser = Featuriser(taxonomy)

    with labels_path.open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("split") == split]

    sidecar = labels_path.with_suffix(labels_path.suffix + ".population.json")
    population = Counter(json.loads(sidecar.read_text())) if sidecar.exists() else Counter()
    drawn = Counter(r["stratum"] for r in rows)

    def weight(stratum: str) -> float:
        if not population or not drawn[stratum]:
            return 1.0
        return population[stratum] / drawn[stratum]

    out = PairSet([], [], [], [], [], {}, {}, {})
    for row in rows:
        label = (row.get("label") or "").strip()
        name = row["raw_name"]
        if not label or label == "unsure":
            continue
        if taxonomy.lookup(name) is not None:
            continue  # exact hits bypass the model at inference

        out.truth[name] = label
        out.baseline[name] = row.get("matcher_guess", "")
        out.strata[name] = row["stratum"]

        ranked = survivors(matcher, name)
        w = weight(row["stratum"])
        for candidate in ranked:
            out.X.append(featuriser.pair(name, candidate, ranked))
            out.y.append(int(candidate.test_id == label))
            out.groups.append(name)
            out.weights.append(w)
            out.candidate_ids.append(candidate.test_id)

    # normalise weights to mean 1 so the regularisation strength is unaffected
    if out.weights:
        mean = sum(out.weights) / len(out.weights)
        out.weights = [w / mean for w in out.weights]
    return out
