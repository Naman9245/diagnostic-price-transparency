"""The shape of one canonical test.

Field choices here are driven by the census finding that lexical similarity is
not sufficient evidence of sameness. Each of `specimen`, `modality`, `views`,
`contrast`, `is_panel` and `analytes` exists because it blocks a specific
confusion that string distance alone gets wrong:

    CBC vs RBC Count                  -> analytes / is_panel
    Troponin I vs Troponin T          -> distinct_from (nothing else separates them)
    Lipid Profile vs Lipid Extended   -> analyte_count
    Vitamin D 25-OH vs 1,25-diOH      -> distinct ids, disjoint aliases
    Serum calcium vs Urine calcium    -> specimen
    X-ray chest PA vs PA + lateral    -> views
    CT abdomen plain vs contrast      -> contrast
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Category(StrEnum):
    HAEMATOLOGY = "haematology"
    CLINICAL_CHEMISTRY = "clinical_chemistry"
    ENDOCRINOLOGY = "endocrinology"
    VITAMINS_MINERALS = "vitamins_minerals"
    SEROLOGY = "serology"
    MICROBIOLOGY = "microbiology"
    IMMUNOLOGY = "immunology"
    COAGULATION = "coagulation"
    CARDIAC_MARKERS = "cardiac_markers"
    TUMOUR_MARKERS = "tumour_markers"
    URINALYSIS = "urinalysis"
    MOLECULAR = "molecular"
    IMAGING = "imaging"
    CARDIOLOGY = "cardiology"


class Kind(StrEnum):
    LAB = "lab"
    IMAGING = "imaging"


class Specimen(StrEnum):
    WHOLE_BLOOD = "whole_blood"
    SERUM = "serum"
    PLASMA = "plasma"
    URINE = "urine"
    URINE_24H = "urine_24h"
    STOOL = "stool"
    SEMEN = "semen"
    SWAB = "swab"
    SPUTUM = "sputum"
    CSF = "csf"
    TISSUE = "tissue"


class Modality(StrEnum):
    RADIOGRAPHY = "radiography"
    ULTRASOUND = "ultrasound"
    DOPPLER = "doppler"
    CT = "ct"
    MRI = "mri"
    MAMMOGRAPHY = "mammography"
    DEXA = "dexa"
    ECG = "ecg"
    ECHOCARDIOGRAPHY = "echocardiography"
    STRESS_TEST = "stress_test"
    PFT = "pft"


@dataclass(frozen=True, slots=True)
class CanonicalTest:
    id: str
    name: str
    category: Category
    kind: Kind

    # --- lab only -------------------------------------------------------
    specimen: Specimen | None = None
    fasting_required: bool | None = None

    # --- imaging only ---------------------------------------------------
    modality: Modality | None = None
    body_region: str | None = None
    views: int | None = None
    contrast: bool | None = None

    # --- panel structure ------------------------------------------------
    # `analytes` is the discriminator: a lipid profile reporting 8 analytes is
    # not the same product as one reporting 5, and pricing them against each
    # other is the same class of error as matching CBC to RBC count.
    is_panel: bool = False
    analytes: tuple[str, ...] = ()
    # Sub-tests that are separately orderable and canonical in their own right.
    components: tuple[str, ...] = ()

    # Curated "these are never the same test" assertions, for pairs that no
    # structural field separates. Troponin I vs Troponin T are both single
    # serum assays in the same category: only a human knows they differ.
    # Declared on either side; the rule layer checks both directions.
    distinct_from: tuple[str, ...] = ()

    loinc: str | None = None
    aliases: tuple[str, ...] = ()
    notes: str | None = None

    @property
    def analyte_count(self) -> int:
        return len(self.analytes)

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.id} ({self.name})"


@dataclass(frozen=True, slots=True)
class Conflict:
    """One reason two canonical tests may never be matched to each other."""

    rule: str
    detail: str


# Fields whose disagreement is disqualifying rather than merely suspicious.
# Consumed by ratecard.normalise.rules; declared here so the taxonomy and the
# matcher cannot drift apart.
BLOCKING_FIELDS: tuple[str, ...] = (
    "distinct_from",
    "specimen",
    "modality",
    "is_panel",
    "views",
    "contrast",
)

ADVISORY_FIELDS: tuple[str, ...] = ("fasting_required", "body_region")

__all__ = [
    "ADVISORY_FIELDS",
    "BLOCKING_FIELDS",
    "CanonicalTest",
    "Category",
    "Conflict",
    "Kind",
    "Modality",
    "Specimen",
]
