"""Phase 03 - build the labelled set, then measure the matcher against it.

The order matters and is not negotiable: label first, tune afterwards. Every
threshold in `normalise.matcher` is an untuned placeholder precisely so that
the 500 labels are drawn before anyone has fitted anything to this corpus.
Fitting first and labelling second produces numbers that mean nothing.
"""

from ratecard.evaluate.metrics import Metrics, evaluate
from ratecard.evaluate.sampling import STRATA, build_sample

__all__ = ["STRATA", "Metrics", "build_sample", "evaluate"]
