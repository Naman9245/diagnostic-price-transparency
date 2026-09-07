"""Read structural attributes out of a free-text test name.

The veto layer in `rules` compares two CanonicalTests. Matching does not have
two of those - it has a raw string on one side. This module is the bridge: it
reads the same attributes out of a string that the taxonomy declares as fields,
so a raw name can be vetoed against a candidate on the same grounds.

    "CT BRAIN PLAIN"        -> modality=ct, contrast=False
    "24 HRS URINE CALCIUM"  -> specimen=urine_24h
    "FREE T3"               -> qualifier=free
    "X RAY CHEST PA & LAT"  -> modality=radiography, views=2

Everything here is a *hint*. An attribute that is absent means unknown, never
false, and two attributes only conflict when both sides actually assert
something. Guessing in either direction would put the veto layer to work
rejecting correct matches, which is worse than the confusion it prevents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ratecard.names import normalise
from ratecard.taxonomy.schema import CanonicalTest, Conflict, Modality, Specimen

# --- lexicons --------------------------------------------------------------
# Ordered where order matters: the first match wins, so the more specific
# phrase must come first.

_SPECIMEN_PHRASES: tuple[tuple[str, Specimen], ...] = (
    ("24 hours urine", Specimen.URINE_24H),
    ("24 hour urine", Specimen.URINE_24H),
    ("24 hrs urine", Specimen.URINE_24H),
    ("24 hr urine", Specimen.URINE_24H),
    ("urine 24 hour", Specimen.URINE_24H),
    ("urine 24 hours", Specimen.URINE_24H),
    ("urinary", Specimen.URINE),
    ("urine", Specimen.URINE),
    ("stool", Specimen.STOOL),
    ("faecal", Specimen.STOOL),
    ("fecal", Specimen.STOOL),
    ("semen", Specimen.SEMEN),
    ("seminal", Specimen.SEMEN),
    ("csf", Specimen.CSF),
    ("cerebrospinal", Specimen.CSF),
    ("sputum", Specimen.SPUTUM),
    ("swab", Specimen.SWAB),
    ("whole blood", Specimen.WHOLE_BLOOD),
    ("plasma", Specimen.PLASMA),
    ("serum", Specimen.SERUM),
)

# CT and MRI are only inferred alongside a region word, because "CT" is also
# how every Indian rate card abbreviates Clotting Time.
_MODALITY_TOKENS: tuple[tuple[frozenset[str], Modality, bool], ...] = (
    (frozenset({"hrct", "cect", "ncct"}), Modality.CT, False),
    (frozenset({"ct"}), Modality.CT, True),
    (frozenset({"mri", "mr"}), Modality.MRI, True),
    (frozenset({"usg", "ultrasound", "ultrasonography", "sonography"}),
     Modality.ULTRASOUND, False),
    (frozenset({"doppler"}), Modality.DOPPLER, False),
    (frozenset({"mammography", "mammogram", "sonomammography"}),
     Modality.MAMMOGRAPHY, False),
    (frozenset({"dexa", "dxa", "densitometry"}), Modality.DEXA, False),
    (frozenset({"echo", "echocardiography"}), Modality.ECHOCARDIOGRAPHY, False),
    (frozenset({"ecg", "ekg", "electrocardiogram"}), Modality.ECG, False),
    (frozenset({"spirometry"}), Modality.PFT, False),
)

_REGION_WORDS = frozenset({
    "brain", "head", "skull", "chest", "thorax", "lung", "abdomen", "pelvis",
    "spine", "lumbar", "cervical", "dorsal", "neck", "knee", "shoulder", "hip",
    "ankle", "wrist", "elbow", "kub", "angiography", "angiogram", "scan",
    "sinus", "pns", "orbit", "temporal", "face", "limb", "leg", "arm",
    "whole", "body", "breast", "scrotum", "thyroid", "liver", "kidney",
})

_XRAY = frozenset({"xray", "x", "ray", "radiograph", "cxr", "axr", "kub"})

_VIEW_PHRASES: tuple[tuple[str, int], ...] = (
    ("pa and lateral", 2),
    ("ap and lateral", 2),
    ("pa lateral", 2),
    ("ap lateral", 2),
    ("both views", 2),
    ("two views", 2),
    ("2 views", 2),
    ("four views", 4),
    ("4 views", 4),
    ("single view", 1),
    ("one view", 1),
    ("pa view", 1),
    ("ap view", 1),
)

_CONTRAST_TRUE = ("with contrast", "contrast enhanced", "cect", "gadolinium",
                  "post contrast")
_CONTRAST_FALSE = ("without contrast", "non contrast", "noncontrast", "plain",
                   "ncct", "hrct")

_QUALIFIERS: tuple[tuple[str, str], ...] = (
    ("free", "free"),
    ("total", "total"),
    ("direct", "direct"),
    ("indirect", "indirect"),
    ("ionised", "ionised"),
    ("ionized", "ionised"),
)

# Indian rate cards abbreviate the glucose family relentlessly, and the
# fasting state is the whole difference between three separately priced rows.
_FASTING: tuple[tuple[str, str], ...] = (
    ("post prandial", "postprandial"),
    ("postprandial", "postprandial"),
    ("ppbs", "postprandial"),
    ("ppbg", "postprandial"),
    ("bspp", "postprandial"),
    ("sugar pp", "postprandial"),
    ("random", "random"),
    ("rbs", "random"),
    ("rbg", "random"),
    ("fasting", "fasting"),
    ("fbs", "fasting"),
    ("fbg", "fasting"),
    ("bsf", "fasting"),
    ("sugar f", "fasting"),
)

_PANEL_WORDS = frozenset({"profile", "panel", "screen"})


@dataclass(frozen=True, slots=True)
class Attributes:
    """What a name asserts about itself. Every field may be None (unknown)."""

    specimen: Specimen | None = None
    modality: Modality | None = None
    contrast: bool | None = None
    views: int | None = None
    qualifier: str | None = None
    fasting: str | None = None
    panel_hint: bool | None = None

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in self.__slots__)


def _first_phrase(text: str, phrases) -> object | None:
    for phrase, value in phrases:
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text):
            return value
    return None


def _modality(text: str, words: frozenset[str]) -> Modality | None:
    for tokens_, modality, needs_region in _MODALITY_TOKENS:
        if words & tokens_:
            if needs_region and not (words & _REGION_WORDS):
                continue
            return modality
    if words & _XRAY and (words & _REGION_WORDS or "xray" in words or "cxr" in words):
        return Modality.RADIOGRAPHY
    return None


def _contrast(text: str) -> bool | None:
    # False wins ties: "plain CT" is unambiguous, and a bare mention of
    # contrast media in a longer string is weaker evidence than "plain".
    if any(phrase in text for phrase in _CONTRAST_FALSE):
        return False
    if any(phrase in text for phrase in _CONTRAST_TRUE):
        return True
    return None


def extract(raw_name: str) -> Attributes:
    """Read every attribute a free-text name asserts about itself."""
    text = normalise(raw_name)
    if not text:
        return Attributes()
    words = frozenset(text.split())

    return Attributes(
        specimen=_first_phrase(text, _SPECIMEN_PHRASES),
        modality=_modality(text, words),
        contrast=_contrast(text),
        views=_first_phrase(text, _VIEW_PHRASES),
        qualifier=_first_phrase(text, _QUALIFIERS),
        fasting=_first_phrase(text, _FASTING),
        panel_hint=True if words & _PANEL_WORDS else None,
    )


def attributes_of(test: CanonicalTest) -> Attributes:
    """Attributes of a canonical test: declared fields win, name fills the gaps.

    The taxonomy declares specimen, modality, contrast and views outright. It
    does not declare "free" versus "total", so that is read from the canonical
    name the same way it is read from a raw one - which is what lets Free T3 be
    vetoed against Total T3 without adding a field for every such pair.
    """
    from_name = extract(test.name)
    return Attributes(
        specimen=test.specimen or from_name.specimen,
        modality=test.modality or from_name.modality,
        contrast=test.contrast if test.contrast is not None else from_name.contrast,
        views=test.views if test.views is not None else from_name.views,
        qualifier=from_name.qualifier,
        fasting=from_name.fasting,
        panel_hint=test.is_panel or from_name.panel_hint,
    )


# Fields that veto a match when both sides assert and disagree. `panel_hint`
# is excluded: "profile" appears in plenty of single-analyte names and the
# false-veto rate was not worth the few real catches.
_COMPARED: tuple[str, ...] = (
    "specimen", "modality", "contrast", "views", "qualifier", "fasting",
)


def conflicts(raw_attrs: Attributes, test: CanonicalTest) -> list[Conflict]:
    """Reasons this raw name cannot be the given canonical test."""
    test_attrs = attributes_of(test)
    out: list[Conflict] = []
    for field_name in _COMPARED:
        mine = getattr(raw_attrs, field_name)
        theirs = getattr(test_attrs, field_name)
        if mine is not None and theirs is not None and mine != theirs:
            out.append(Conflict(f"attr_{field_name}", f"name says {mine}, {test.id} is {theirs}"))
    return out


def vetoes(raw_name: str, test: CanonicalTest) -> bool:
    """True when the raw name's own words rule this candidate out."""
    return bool(conflicts(extract(raw_name), test))
