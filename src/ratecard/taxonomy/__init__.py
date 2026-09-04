"""The canonical test taxonomy (Phase 01).

The taxonomy is the thing every price observation resolves to. It is
hand-curated YAML under `data/`, loaded and validated by `loader.load`.
"""

from ratecard.taxonomy.loader import Taxonomy, ValidationError, load
from ratecard.taxonomy.schema import CanonicalTest, Category, Modality, Specimen

__all__ = [
    "CanonicalTest",
    "Category",
    "Modality",
    "Specimen",
    "Taxonomy",
    "ValidationError",
    "load",
]
