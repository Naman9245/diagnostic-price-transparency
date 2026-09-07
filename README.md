# Bengaluru Rate Card

Hyperlocal diagnostic price comparison for Bengaluru. A doctor writes "CBC and
lipid profile" on a slip; this tells you what those cost at labs near you, and
shows the document each number came from.

The technical core is **name normalisation**, not OCR. Across sources the same
test appears as `COMPLETE BLOOD COUNT (CBC)`, `CBC`, and `Complete Blood Count`
— and separately as `RED BLOOD CELL COUNT`, which is not the same test and is
priced differently. Until names resolve to a canonical entity, no two prices
can be compared and the product does not exist.

## Status

| Phase | | |
|---|---|---|
| 00 Seed corpus | rebuilt 4 Sep | 12,993 rows, 11,682 distinct names, 4 source documents |
| 01 Canonical taxonomy | in progress | 210 tests, validating, **exit criterion needs restating — see below** |
| 02 The matcher | built, untuned | 17.2% of rows resolved, 204/210 canonical tests hit |
| 03 Label and evaluate | not started | the deliverable |

## Architecture

Six stages, one direction. Everything upstream of the database is a batch
pipeline replayable from immutable raw files; everything downstream is a
conventional read-heavy API.

```
1 registry  ->  2 fetch  ->  3 parse  ->  4 normalise  ->  5 geo  ->  6 api
   YAML         httpx        pdfplumber     rapidfuzz       PostGIS   FastAPI
                sha256       selectolax     MiniLM          Nominatim Next.js
```

`src/ratecard/` mirrors those stages one directory each. Stage 4 and the
taxonomy carry implementation today; stages 1-3 and 5-6 are seams.

## Stage 4: the matcher

```bash
.venv/bin/ratecard match data/corpus/phase00.csv --out data/interim/matched.csv
```

Four layers, in order:

| | | |
|---|---|---|
| 0 | exact | alias-index hit, confidence 1.0, needs no review |
| 1 | candidates | `token_set_ratio` generates, `WRatio` ranks |
| 2 | veto | attribute conflicts + the taxonomy's declared-distinct rules |
| 3 | rerank | *optional* sentence-transformer cosine similarity |

The two-scorer split in layer 1 is not decoration. `token_set_ratio` returns a
flat 100 whenever one token set is a subset of the other, which tied `urea`
against `bun` at 100 apiece on "blood urea nitrogen bun". `token_sort_ratio`
fixes that but over-punishes elaboration, scoring "esr automated westergren
erythrocyte sedimentation rate" against "esr" at 10. On a seven-case
discrimination set WRatio ranked 7/7 correctly, token_sort 6/7, token_set 4/7.

Layer 2 needed a bridge: `rules` compares two canonical tests, but matching has
a raw string on one side. `normalise/attributes.py` reads the same attributes
out of free text that the taxonomy declares as fields — so "CT BRAIN PLAIN"
carries `contrast=False` and vetoes `ct_brain_contrast`, and "24 HRS URINE FOR
CALCIUM" carries `specimen=urine_24h` and vetoes `calcium_serum`. Absence of an
attribute means unknown, never false; two attributes conflict only when both
sides assert something.

### Current numbers, untuned

```
ROWS     2241/12993   17.2% resolved
NAMES    1871/11682   16.0% resolved
canonical tests hit    204/210 (97%)

  abstain_no_candidate   58.8%     abstain_low_score     6.1%
  abstain_thin_margin    17.9%     exact                 2.3%
  lexical                13.7%     abstain_vetoed        1.2%
```

**The thresholds are untuned placeholders and must stay that way until Phase
03.** Labelling 500 pairs *after* fitting thresholds to this corpus would make
the evaluation meaningless. The abstention rate is high on purpose: most of
`abstain_no_candidate` is surgery, chemotherapy and specialist assays that
genuinely are not in a 210-test routine taxonomy, and silence is the correct
answer for those.

**17.2% resolved is not 17.2% correct.** See below.

### What the embedding rerank actually does

Off by default (`--rerank` to enable). On a 1,500-name random sample it changes
the answer 215 times, and the direction is one-sided:

```
rerank RESOLVED what lexical refused :  11
rerank REFUSED what lexical resolved : 204
rerank picked a DIFFERENT test       :   0
```

It is a **precision filter, not a recall booster**. Twelve of those refusals
were inspected by hand and all twelve were lexical errors:

| raw name | lexical said | rerank |
|---|---|---|
| `CT ELBOW RIGHT` | `clotting_time` | refuses |
| `OT CHARGES - PER 15 MINS (3-6 HRS)` | `ca_15_3` | refuses |
| `LUMBAR DRAIN` | `xray_lumbar_spine` | refuses |
| `FACTOR VII ASSAY` | `rheumatoid_factor` | refuses |
| `herpes simplex virus igg serum` | `lh` | refuses |
| `PLEURAL FLUID FOR CELL COUNT` | `rbc_count` | refuses |

Twelve of 204 is not a measurement, and some of the other 192 are certainly
correct matches being lost. But it does say the lexical layer is confidently
wrong often enough that the headline resolution figure overstates it, and that
the rerank's job here is subtraction. Phase 03 is what turns this into numbers.

One design note. The rerank **blends** with the lexical score rather than
replacing it. Substituting it outright collapsed the spread between candidates
— MiniLM cosine similarities on short medical phrases rarely leave 0.5–0.95 —
so nearly everything fell inside the thin-margin window and rows that had been
resolving correctly (`blood urea nitrogen bun`, `serum electrolytes (na k cl)`)
regressed to abstentions.

## Phase 01: the taxonomy

`src/ratecard/taxonomy/data/*.yaml` — 210 hand-curated canonical tests across
14 categories, 1,046 indexed surface forms. The last 19 were added from the
Phase 00 coverage worklist: names appearing in three or four sources that the
taxonomy did not cover.

Every field on a canonical test exists to block a specific confusion that
string distance gets wrong:

| Confusion | Blocked by |
|---|---|
| CBC vs RBC Count | `is_panel` |
| Lipid Profile vs Lipid Profile Extended | `analytes` (5 vs 9) |
| Thyroid Profile vs Free Thyroid Profile | `analytes` (same count, different set) |
| Serum Albumin vs Urine Microalbumin | `specimen` |
| X-ray chest PA vs PA + lateral | `views` |
| CT brain plain vs contrast | `contrast` |
| Clotting Time ("CT") vs CT Brain | `kind` |
| Troponin I vs Troponin T | `distinct_from` |
| Vitamin D 25-OH vs 1,25-diOH | `distinct_from` |

`distinct_from` is the curated escape hatch for pairs no structural field
separates. It is deliberately explicit: it makes "a human decided these differ"
visible in the data rather than buried in a threshold.

### Fasting state is advisory, not a veto

It began as a hard rule and was demoted. It blocked ferritin against serum iron
— two genuinely different tests, but different for reasons having nothing to do
with fasting. Labs also disagree about whether a lipid profile requires it, so
a veto would reject correct cross-source matches. The one family where fasting
state *is* the test identity is glucose, and that is handled by explicit
`distinct_from` declarations rather than by a general principle.

## Usage

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

.venv/bin/ratecard validate            # exit non-zero if the taxonomy is broken
.venv/bin/ratecard stats               # categories, panels, LOINC gaps
.venv/bin/ratecard lookup "haemogram" "sugar F" "USG whole abdomen"
.venv/bin/ratecard check cbc rbc_count # why two tests may never be matched
.venv/bin/ratecard hard-negatives      # seed pairs for the Phase 03 eval set
.venv/bin/ratecard coverage data/corpus/phase00.csv
```

Phase 01 runs on stdlib plus PyYAML alone, so `validate` works on a bare
machine. Heavier stages are optional extras in `pyproject.toml`.

## Phase 00, rebuilt

`scripts/phase00_seed_corpus.py --fetch` rebuilds the corpus from scratch:
downloads the sources, verifies their sha256, extracts the PDF text, writes
`data/corpus/phase00.csv`.

| Source | | |
|---|---|---|
| Narayana — Mazumdar Shaw, Bengaluru | 120pp PDF | 5,866 priced rows |
| Narayana — Guwahati | 63pp PDF | 1,674 rows, `display_ok=False` |
| Lal PathLabs sitemaps | XML | 3,099 names |
| Redcliffe sitemaps | XML | 2,354 names |

Two things improved on the original census. **The Bengaluru unit file was
found** — Mazumdar Shaw Medical Center, Narayana Health City, effective Jan
2024 — replacing the Guwahati document the census mistakenly treated as a
Bengaluru price. Guwahati is kept for name harvesting and flagged
`display_ok=False` so its numbers can never reach a public view. And **only
sitemaps are fetched**, never per-test pages: both lab chains put the test name
in the URL slug, so ~20 requests replace ~7,000.

robots.txt was checked for all three publishers on 2026-09-04. Narayana and Lal
PathLabs both `Allow: /`; Redcliffe disallows only campaign and landing paths.
Nothing fetched here is disallowed.

### The two units use different tier schemas

Bengaluru quotes **11** prices per row, Guwahati **8**:

```
Bengaluru  OPD | General (C) | Semi Private | SEMI DELUXE | Private |
           PLATINUM-B | PLATINUM-A | PLATINUM SUITE | CCA | HDU | SDU
Guwahati   OPD | General C | General | Semi Private | Private | Deluxe | CCA | NICU
```

Column one is the OPD walk-in rate in both, which is the tier the corpus loads
as `price`. But `price_tier` cannot be a shared enum across publishers — the
tier vocabulary is per-document, and Stage 3 will have to carry the source's own
column header rather than normalise it away.

## Three things that are not done

**The Phase 01 exit criterion no longer fits its corpus.** It was written as
"taxonomy covering 80%+ of the corpus by row volume" on the assumption that the
corpus was a list of diagnostic tests. It is not. The Bengaluru document is a
hospital's entire billable catalogue — 78 surgery rows, 45 implants, 25
dialysis, 18 amputations, bed charges, admission fees — and the lab chains list
thousands of specialist assays (allergy panels, FISH rearrangements,
immunohistochemistry markers). A 210-test routine taxonomy measured against all
13,000 rows currently reports:

```
exact       381 rows   2.9%   correct by construction
reachable  2232 rows  17.2%   containment heuristic, over-counts
```

Both numbers are honest and neither is the interesting one. The useful measure
runs the other way: **148 of 210 canonical tests (70%) appear in the corpus by
exact match alone**, which says the taxonomy describes tests that really exist
in real price lists. Most of the 62 that do not are present under a different
word order — `lactate dehydrogenase ldh`, `blood urea nitrogen bun`, `hdl
cholesterol direct` — which is exactly what the Phase 02 matcher's token-set
pass closes for free.

The criterion needs restating before Phase 01 can be called done. Chasing 80%
of *this* corpus would mean curating thousands of oncology and surgical entries
for a product about routine prescriptions, which is the wrong project.

**LOINC codes are unverified.** Most lab tests carry a code, seeded from
memory rather than from a fetched LOINC release. They must be checked against
loinc.org before Phase 03, and any that do not map cleanly should be set to
null rather than approximated. Imaging carries no codes at all, deliberately —
a guessed code is worse than an absent one.

## Coverage is reported as two numbers

`ratecard coverage` prints `exact` and `reachable` and passes on `exact`:

- **exact** — resolved by alias lookup alone. Correct by construction.
- **reachable** — a token-containment heuristic, a loose ceiling on what the
  Phase 02 matcher could reach. It over-counts and is not a correctness claim.

The real number sits between them and cannot be known until the matcher and the
labelled set exist. Quoting `reachable` as the exit criterion would be
dishonest, so the tool refuses to.
