# Bengaluru Rate Card

Hyperlocal diagnostic price comparison for Bengaluru. A doctor writes "CBC and
lipid profile" on a slip; this tells you what those cost at labs near you, and
shows the document each number came from.

The technical core is **name normalisation**, not OCR. Across sources the same
test appears as `COMPLETE BLOOD COUNT (CBC)`, `CBC`, and `Complete Blood Count`
— and separately as `RED BLOOD CELL COUNT`, which is not the same test and is
priced differently. Until names resolve to a canonical entity, no two prices
can be compared and the product does not exist.

## Documentation

| | |
|---|---|
| [docs/product.md](docs/product.md) | what the app does, who it is for, and what it is not |
| [docs/architecture.md](docs/architecture.md) | the six stages, the data model, and why each choice |
| [docs/matching.md](docs/matching.md) | **how the ML works** — the four layers, the veto, the evaluation |
| [docs/curating-the-taxonomy.md](docs/curating-the-taxonomy.md) | how to add a test or an alias |
| [CLAUDE.md](CLAUDE.md) | working context: current phase, rules, traps already hit |

## Status

| Phase | | |
|---|---|---|
| 00 Seed corpus | rebuilt 4 Sep | 13,112 rows, 11,648 distinct names, 4 source documents |
| 01 Canonical taxonomy | done | 210 tests, validating; exit criterion restated — see below |
| 02 The matcher | built, untuned | 20.7% of rows resolved, 205/210 canonical tests hit |
| 03 Label and evaluate | tooling ready, 0/500 labelled | **the deliverable** |

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
ROWS     2716/13112   20.7% resolved
NAMES    2298/11755   19.5% resolved
canonical tests hit    205/210 (98%)

  abstain_no_candidate   58.7%     abstain_low_score     6.0%
  abstain_thin_margin    14.5%     exact                 2.3%
  lexical                17.3%     abstain_vetoed        1.3%
```

Only an **exact alias hit** is trusted without review. Everything else carries
`needs_review`, however high it scored — see the review notes below.

**The thresholds are untuned placeholders and must stay that way until Phase
03.** Labelling 500 pairs *after* fitting thresholds to this corpus would make
the evaluation meaningless. The abstention rate is high on purpose: most of
`abstain_no_candidate` is surgery, chemotherapy and specialist assays that
genuinely are not in a 210-test routine taxonomy, and silence is the correct
answer for those.

**20.7% resolved is not 20.7% correct.** See below.

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
| Narayana — Mazumdar Shaw, Bengaluru | 120pp PDF | 5,898 priced rows |
| Narayana — Guwahati | 63pp PDF | 1,761 rows (31 unparsed, reported), `display_ok=False` |
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

## Phase 03: labelling and evaluation

```bash
.venv/bin/ratecard sample data/corpus/phase00.csv   # already drawn, 500 rows
.venv/bin/ratecard label  data/eval/labels.csv --by you   # read the worked examples first
.venv/bin/ratecard evaluate data/eval/labels.csv
```

The set is drawn: 500 rows, 345 train / 155 holdout, seeded and reproducible.

**It is stratified, not uniform, and that is load-bearing.** A uniform draw
from 11,755 names would be dominated by surgical procedures where the answer is
"none", and 350 labels proving the matcher declines to match `ABOVE ELBOW
AMPUTATION` teach nothing. Each stratum is drawn to a quota chosen for what it
can teach:

| stratum | drawn | of | why |
|---|---|---|---|
| `exact` | 60 | 268 | are the aliases themselves right? |
| `lexical` | 140 | 2,030 | the risk surface: confident answers that may be wrong |
| `abstain_thin_margin` | 100 | 864 | near-misses; the veto layer's home ground |
| `declared_distinct_neighbour` | 40 | 842 | top two are a curated hard-negative pair |
| `abstain_low_score` | 60 | 709 | did we refuse something we should have taken? |
| `abstain_no_candidate` | 60 | 6,895 | mostly true negatives; confirms the floor |
| `abstain_vetoed` | 40 | 146 | did a hard rule over-fire? |

The consequence: rates measured on this sample are **not** corpus rates.
`Metrics.corpus_estimate` reweights per-stratum rates by the true sizes above,
and the naive pooled number is never reported as a corpus figure. Those sizes
are written to `labels.csv.population.json` when the sample is drawn — without
that sidecar no corpus estimate is possible, and `ratecard evaluate` says so
rather than quoting a stratified rate as a corpus rate.

**[docs/labelling-worked-examples.md](docs/labelling-worked-examples.md)** works
fifteen real rows through end to end — the specimen rule, the view-count pair,
when to press `u`, and the two cases where the matcher's abstention was wrong.
All but one are drawn from outside the sample so reading it anchors nothing,
and a test enforces that.

### Two things the labelling tool does deliberately

**The matcher's answer is hidden.** The candidate pool is shown — 210 options
is more than anyone can hold in their head — but not which candidate the
matcher picked, nor its score, and the list is sorted by id rather than by rank.
A labeller shown "the machine thinks this is `cbc`, agree?" agrees far more
often than they should, and that inflates the exact number this exercise exists
to measure honestly.

**Nothing is ever lost.** The file is rewritten through a temp file after every
single label, and the session resumes from the first unlabelled row. `s` skips,
`q` saves and quits, `?text` searches the taxonomy, `=id` enters an id directly.

### What gets reported

Five outcomes, because "accuracy" hides the distinction that matters:
`correct_match`, `wrong_match`, `missed`, `correct_abstention`, `unsure`.

Every rate carries a **95% Wilson interval and its n**, because the strata are
small and a bare percentage off 26 rows is not a measurement. Wilson rather
than the normal approximation: these proportions sit near 1, where the normal
interval misbehaves and can run outside [0, 1] entirely.

`evaluate` works on a partly-labelled file, so the numbers sharpen as you go
rather than arriving all at once at row 500. It refuses to let a wide interval
pass as a finding — anything over 20 points wide is called out as too few
labels to conclude, with an estimate of how many more would halve it.

What the sample can actually buy, once the train split is labelled:

| measure | n | interval at p≈0.90 |
|---|---|---|
| overall precision | 143 | ±5 pts |
| hard-negative accuracy | 96 | ±6 pts |
| abstention precision | 106 | ±6 pts |
| `declared_distinct` alone | 26 | **±12 pts** |

The first three are quotable. The last is not — 26 rows cannot support a
separate headline number, so `declared_distinct` is reported only as part of
the hard slice, not on its own.

A missed row shows the user nothing. A wrong row shows them a confident price
for the wrong test — the one failure this project exists to prevent. So
precision leads, and the headline claim should be a precision figure at a
stated coverage, with **hard-negative accuracy reported separately**. That
second number is the interesting one.

`data/eval/` is committed. Regenerating the sample is cheap; re-labelling 500
rows is not.

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
reachable  2223 rows  17.0%   containment heuristic, over-counts
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

**~~LOINC codes are unverified~~ — done.** All 145 were checked on 2026-09-13
against the NLM Clinical Table Search Service, a free public endpoint over the
official LOINC table. The result argues for the rule rather than against it:

```
12 codes did not exist in LOINC at all
 2 pointed at the wrong analyte
```

`ace` was `1979-4`, which is *Biopterin in 24-hour urine*. The two Coombs codes
were on each other's tests, and that one slipped past name-similarity triage
because "Direct antiglobulin test" and "Indirect Coombs Test" share enough
words. Most fabrications were **one digit off** a real code — `38476-0` for
`38476-8`, `32546-6` for `32546-4`, `1763-6` for `1763-2` — which is precisely
the shape that survives a plausibility check and fails a lookup.

14 are corrected, 2 nulled where no confident match was found, and 15 more are
recorded as reviewed synonyms (LOINC names the analyte, Indian rate cards name
the assay: VDRL is *Reagin Ab by RPR*, calcitriol is *1,25-dihydroxyvitamin D*).
`python scripts/verify_loinc.py` re-checks the lot; a clean run reports zero
and zero. Imaging still carries no codes, deliberately.

## Coverage is reported as two numbers

`ratecard coverage` prints `exact` and `reachable` and passes on `exact`:

- **exact** — resolved by alias lookup alone. Correct by construction.
- **reachable** — a token-containment heuristic, a loose ceiling on what the
  Phase 02 matcher could reach. It over-counts and is not a correctness claim.

The real number sits between them and cannot be known until the matcher and the
labelled set exist. Quoting `reachable` as the exit criterion would be
dishonest, so the tool refuses to.


## Review notes

A review on 2026-09-09 found six bugs. Each now has a regression test in
`tests/test_regressions.py` that fails against the code as it was.

**`"a"` was a stopword.** In a domain of Vitamin A, Hepatitis A, Influenza A
and Apo A1. `normalise("Vitamin A")` returned `"vitamin"` and `"vit A"`
returned `"vit"`, so a bare `VITAMIN` row exact-matched Vitamin A at confidence
1.0 and needed no review. A stopword list must never eat a single letter here.

**`needs_review` waved through 212 lexical guesses.** It read
`test_id is None or method != "exact" and confidence < 95.0`, which parses as
`A or (B and C)`, and WRatio emits exactly 95.0 for a very common partial
alignment. Among the exempted: `BLOOD CULTURE FOR FUNGUS` resolving to
`fungal_culture`, whose specimen is tissue rather than blood. Only exact hits
skip review now.

**The 31 `distinct_from` declarations were inert.** `_apply_vetoes` claimed in
its docstring to use them and never did; `rules.blocks` appeared only in a log
message. 109 matches were accepted over a curated-distinct runner-up within 12
points. A close curated pair is now resolved by *evidence* — a word in the raw
name belonging to one of the pair and not the other, so `blood urea nitrogen
bun` resolves on "bun" while a bare `TROPONIN` abstains, carrying nothing to
separate troponin I from troponin T.

**Phase 00 silently dropped 323 rows.** Long names wrap in the PDF text layer
and the price run lands on the next line, so the row regex simply missed them —
291 of Guwahati's 1,792 priced rows, 16% of that source, plus 32 in Bengaluru.
A second row format also exists in the same document, with the service type
trailing the prices rather than leading. Both are handled, and anything still
unparsed is now *counted in the output* instead of vanishing.

**`corpus_estimate` could never return a number.** Stratum populations were
computed at sample time and thrown away, so the reweighting documented above
returned `None` on every call and nothing ever called it.

**Dead code describing behaviour that was not there.** `coverage.py` sorted
surface forms longest-first and explained that this let the more specific study
win, but the only caller asks `any(...)`, which is order-independent. Plus an
unused `SKIP` sentinel and an unused `raw_name` parameter.
