"""Name normalisation, shared by the taxonomy and the Stage 4 matcher.

Every raw test name from every source funnels through `normalise` before it is
compared to anything. The taxonomy's alias index is built with the same
function, so an alias collision found at load time is a collision the matcher
would really have hit.

The rule here is *conservative*. Normalisation may only remove noise that
cannot distinguish two tests. It must never collapse a real distinction:
`vitamin d 25 hydroxy` and `vitamin d 1 25 dihydroxy` are different tests
priced Rs 2,890 and Rs 2,800, and no amount of tidying may merge them.
"""

from __future__ import annotations

import re
import unicodedata

# British -> American, applied on whole words only. Indian lab documents mix
# both spellings freely, often inside one PDF.
_SPELLING = {
    "haemoglobin": "hemoglobin",
    "haemogram": "hemogram",
    "haematology": "hematology",
    "haematocrit": "hematocrit",
    "haemat": "hemat",
    "anaemia": "anemia",
    "leucocyte": "leukocyte",
    "leukocytes": "leukocyte",
    "oestrogen": "estrogen",
    "oestradiol": "estradiol",
    "paediatric": "pediatric",
    "foetal": "fetal",
    "sulphate": "sulfate",
    "tumour": "tumor",
    "gynaecology": "gynecology",
    "coeliac": "celiac",
    "diarrhoea": "diarrhea",
    "oedema": "edema",
    "caesarean": "cesarean",
}

# Noise that carries no discriminating power in any source seen so far.
# Deliberately short. "profile", "panel" and "screen" are NOT here - they are
# exactly what separates `lipid` from `lipid profile extended`.
_STOPWORDS = frozenset({"test", "tests", "investigation", "investigations", "the", "a", "of"})

_PUNCT = re.compile(r"[^\w\s]+")
_SPACES = re.compile(r"\s+")
# Rs 450 / INR 450 / 450.00 style price fragments that leak out of table cells.
_CURRENCY = re.compile(r"(?:₹|\brs\.?\b|\binr\b)\s*[\d,]+(?:\.\d+)?", re.IGNORECASE)


def _fold_unicode(text: str) -> str:
    """NFKD-fold, keeping the rupee sign long enough for _CURRENCY to see it."""
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return unicodedata.normalize("NFKC", text)


def normalise(raw: str) -> str:
    """Return the canonical comparison form of a raw test name.

    Lowercased, unicode-folded, spelling-normalised, punctuation stripped,
    whitespace collapsed. Idempotent: normalise(normalise(x)) == normalise(x).

    >>> normalise("COMPLETE BLOOD COUNT (CBC)")
    'complete blood count cbc'
    >>> normalise("Haemoglobin - Rs 150")
    'hemoglobin'
    >>> normalise("T3/T4/TSH")
    't3 t4 tsh'
    """
    if not raw:
        return ""

    text = _fold_unicode(raw).lower()
    text = _CURRENCY.sub(" ", text)
    text = _PUNCT.sub(" ", text)

    tokens = []
    for token in _SPACES.split(text):
        if not token or token in _STOPWORDS:
            continue
        tokens.append(_SPELLING.get(token, token))

    return " ".join(tokens)


def alias_key(raw: str) -> str:
    """Key under which a name is indexed for exact lookup.

    Identical to `normalise` today, kept separate because the matcher may later
    want a lossier key (token-sorted, say) without changing what the taxonomy
    validator treats as a collision.
    """
    return normalise(raw)


def tokens(raw: str) -> frozenset[str]:
    """Normalised token set, for coverage heuristics and candidate blocking."""
    return frozenset(normalise(raw).split())
