"""Hard rules that veto a match regardless of similarity score.

Every rule here corresponds to a confusion the census actually found in the
corpus, not a hypothetical one. Each returns a Conflict naming itself so a
blocked match can be explained in the review queue rather than silently
disappearing.
"""

from __future__ import annotations

from ratecard.taxonomy.schema import CanonicalTest, Conflict


def _declared_distinct(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """A curator has asserted these two are different tests.

    The escape hatch for pairs no structural field separates: Troponin I vs
    Troponin T, Vitamin D 25-OH vs 1,25-diOH, Widal vs Typhidot. Declared on
    either side and honoured in both directions.
    """
    if b.id in a.distinct_from or a.id in b.distinct_from:
        return Conflict("declared_distinct", f"{a.id} and {b.id} are curated as distinct")
    return None


def _specimen(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """Serum calcium is not urine calcium; serum albumin is not microalbumin."""
    if a.specimen is not None and b.specimen is not None and a.specimen != b.specimen:
        return Conflict("specimen", f"{a.specimen} vs {b.specimen}")
    return None


def _kind(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """A blood test is never an imaging study, however the letters line up."""
    if a.kind != b.kind:
        return Conflict("kind", f"{a.kind} vs {b.kind}")
    return None


def _modality(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    if a.modality is not None and b.modality is not None and a.modality != b.modality:
        return Conflict("modality", f"{a.modality} vs {b.modality}")
    return None


def _panel(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """CBC is not RBC count. A panel is never one of its own members."""
    if a.is_panel != b.is_panel:
        panel, single = (a, b) if a.is_panel else (b, a)
        return Conflict("panel_vs_single", f"{panel.id} is a panel, {single.id} is not")
    return None


def _panel_composition(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """Lipid profile is not lipid profile extended.

    Two panels with different analyte sets are different products even when
    one wholly contains the other - especially then, because containment is
    exactly what makes the names look alike.
    """
    if not (a.is_panel and b.is_panel):
        return None
    if set(a.analytes) != set(b.analytes):
        return Conflict(
            "panel_composition",
            f"{a.id} has {a.analyte_count} analytes, {b.id} has {b.analyte_count}",
        )
    return None


def _views(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """Chest X-ray PA is not chest X-ray PA and lateral."""
    if a.views is not None and b.views is not None and a.views != b.views:
        return Conflict("views", f"{a.views} view(s) vs {b.views} view(s)")
    return None


def _contrast(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """Plain CT is not contrast CT, and the price gap is roughly double."""
    if a.contrast is not None and b.contrast is not None and a.contrast != b.contrast:
        return Conflict("contrast", f"contrast={a.contrast} vs contrast={b.contrast}")
    return None


def _fasting(a: CanonicalTest, b: CanonicalTest) -> Conflict | None:
    """Advisory only. See ADVISORY_RULES below for why this does not veto."""
    if (
        a.fasting_required is not None
        and b.fasting_required is not None
        and a.fasting_required != b.fasting_required
    ):
        return Conflict("fasting_state", f"fasting={a.fasting_required} vs {b.fasting_required}")
    return None


# Vetoes. Each is a structural fact about what the test *is*.
RULES = (
    _declared_distinct,
    _kind,
    _specimen,
    _modality,
    _panel,
    _panel_composition,
    _views,
    _contrast,
)

# Signals worth surfacing in the review queue but not worth vetoing on.
#
# Fasting state started life as a veto and was demoted, because it blocked
# ferritin against serum iron - two genuinely different tests, but different
# for reasons that have nothing to do with fasting. Fasting is preparation
# metadata, not identity: labs disagree about whether a lipid profile needs it,
# and a rule that vetoes on it would reject correct matches across sources.
#
# The one family where fasting *is* identity-bearing is glucose, where the
# fasting state is the test name. That is handled by explicit distinct_from
# declarations on glucose_fasting, which is honest about being curated
# knowledge rather than a general principle.
ADVISORY_RULES = (_fasting,)


def explain(a: CanonicalTest, b: CanonicalTest) -> list[Conflict]:
    """Every reason these two may not be matched. Empty means no rule objects."""
    if a.id == b.id:
        return []
    return [conflict for rule in RULES if (conflict := rule(a, b)) is not None]


def advisories(a: CanonicalTest, b: CanonicalTest) -> list[Conflict]:
    """Soft signals: not disqualifying, but worth flagging for review."""
    if a.id == b.id:
        return []
    return [conflict for rule in ADVISORY_RULES if (conflict := rule(a, b)) is not None]


def blocks(a: CanonicalTest, b: CanonicalTest) -> bool:
    """True when any hard rule forbids matching `a` to `b`."""
    return bool(explain(a, b))
