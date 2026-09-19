# Worked examples for labelling

Fifteen real rows, reasoned through end to end. **Every one but the last is
drawn from outside the 500-row sample**, so reading this cannot anchor a row
you will actually label. The exception is `madurai`, which is named on purpose
because it is a known dud sitting in the sample and telling you to press `n` on
it costs nothing. Both claims are enforced by `tests/test_docs.py` — a document
that says something load-bearing should be checked, not trusted.

The question you are answering is always the same, and it is *not* "did the
matcher get it right":

> Which canonical test is this name, if any?

Answer with a canonical id, `n` for none, or `u` for unsure. `u` is excluded
from the metrics and reported separately, so use it freely — a forced guess is
worse than an admitted gap.

---

## The one rule that settles most cases

**Same name is not same test.** Specimen, panel size, view count, contrast and
fasting state are part of the identity. If any of them differ, it is a
different test, however similar the words.

---

## Easy: the alias is genuinely right

| raw name | label | why |
|---|---|---|
| `cholesterol test` | `cholesterol_total` | Unqualified cholesterol means total. "test" is noise. |
| `usg of neck` | `usg_neck` | "of" is stripped by normalisation. Same study. |
| `glucose post prandial` | `glucose_postprandial` | Exactly the test. |

These are the `exact` stratum. You are checking **the alias**, not the matcher —
if a surface form is wrong, that is a taxonomy bug worth catching.

## Shared word, different test

**`bone marrow iron stain` → `n`**

Shares "iron" with `serum_iron`, and nothing else. This is a histological stain
on a marrow aspirate; serum iron is a chemistry assay on blood. Different
specimen, different method, different price. The word overlap is a coincidence.

**`urea fluid` → `n`**

Urea measured in body fluid, not serum. `urea` is specimen `serum`. There is no
canonical entry for fluid urea, so the answer is none — *not* `urea`.

> If you find yourself thinking "well, it's basically the same thing", check
> the specimen. That is usually what is nagging at you.

## The view-count pair — read these two together

**`digital xray ls spine ap lat` → `xray_lumbar_spine`**

AP and lateral, two views. `xray_lumbar_spine` declares `views: 2`. Match.

**`XRAY LUMBO SACRAL SPINE LAT` → `n`**

Lateral only. One view. The canonical is a two-view study and is priced as one.
Same region, same modality, same words almost — and a different product.

This pair is the whole reason `views` exists as a field. If you label the
second one `xray_lumbar_spine` because it is "close enough", the comparison
table will eventually show someone a two-view price for a one-view study.

## Ambiguity that is genuinely unresolvable

**`dengue fever panel comprehensive` → `u`**

There is a `dengue_panel` (NS1 + IgM + IgG). Is "comprehensive" the same three
analytes, or more? The source does not say, and two labs use the word
differently. This is the same trap as `lipid profile complete`, which is
deliberately left unaliased for exactly this reason.

`u`, not a guess. The unsure count is itself a finding — it measures how much
of the corpus is irreducibly ambiguous without contacting the lab.

## Correct abstentions

| raw name | label | why |
|---|---|---|
| `filaria antibody igg` | `n` | Real test, not in a 210-test routine taxonomy. |
| `fish 22q deletion or lsi di george vcfs` | `n` | Specialist cytogenetics. Not routine. |
| `calcium 24 hrs urine` | `n` | 24-hour urine calcium. `calcium_serum` is serum. No canonical entry exists. |

The matcher abstained on all three and was right. Confirming a correct
abstention is as valuable as catching an error — `abstention_precision` is a
reported number.

## Abstentions that were wrong

**`xray lumbar spine ap lat` → `xray_lumbar_spine`**

Two views, matches the canonical exactly in substance. The matcher scored it
below threshold and refused. That is a **miss**, and misses are what tell you
the threshold is set too high. Label the truth, not the matcher's opinion.

Note this is near-identical to `digital xray ls spine ap lat`, which the
matcher *did* resolve. Inconsistency like that is exactly what the labelled set
is for.

**`MRI BRAIN FULL STUDY AFTER SCREENING PLAIN 3T` → `mri_brain_plain`**

"Plain" is explicit, region is brain, modality is MRI. "Full study after
screening" is protocol detail and "3T" is field strength — neither changes
which test it is. The matcher abstained; it should not have.

## A veto that was right about the wrong thing

**`CSF GRAM STAIN` → `n`**

The matcher vetoed `gram_stain` because that entry declares specimen `swab` and
this is CSF. The veto fired correctly.

But the *reason* it is `n` is that the taxonomy has no CSF gram stain, not that
a gram stain on CSF is a different procedure. Worth a note in the `note` column:
this is a taxonomy gap, not a matcher error. Those notes are how Phase 04 knows
what to add.

## Crawl noise

**`madurai` → `n`**

A city landing page harvested as though it were a test name. There were 139 of
these; the extraction now filters them and only this one survives in the
sample. Label it `n` and move on.

If you meet anything else that is plainly not a test — a bare code, a
fragment — it is `n`.

---

## When you are stuck

1. **Check the specimen first.** It resolves more cases than anything else.
2. **Count the analytes** if either side is a panel.
3. **`?search` the taxonomy** before concluding `n` — the answer may be under a
   name you did not think of. `?urine`, `?calcium`, `?spine`.
4. **Still unsure after thirty seconds?** Press `u` and move on. That is what it
   is for, and dithering over one row costs more than the row is worth.

The set is 500 rows. It does not have to be one sitting — `q` saves, and
`ratecard evaluate` reports what the rows you have done already support.
