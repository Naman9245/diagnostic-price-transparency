# Bengaluru Rate Card

Hyperlocal diagnostic price comparison for India. Someone is holding a doctor's
slip that says "CBC and lipid profile"; this shows what those cost at labs near
them, with the source document behind every number.

The technical core is **name normalisation, not OCR**. Sources have digital
text layers, so extraction is the easy part. Resolving `COMPLETE BLOOD COUNT
(CBC)` / `CBC` / `Complete Blood Count` to one entity — while keeping `RED
BLOOD CELL COUNT` separate — is the whole problem.

## Where things stand

| Phase | State |
|---|---|
| 00 Seed corpus | done — 13,112 rows, 11,648 distinct names, 4 source documents |
| 01 Taxonomy | done — 210 canonical tests, validating |
| 02 Matcher | built, **untuned** — 20.7% of rows resolved, 205/210 tests observed |
| 03 Label & evaluate | **blocked on human labelling** — 500 rows drawn, 0 labelled |
| 04–07 | not started (pipeline, geo/DB/API, UI, provenance) |

Phase 03 is the deliverable. Everything after it is ordinary engineering.

## Commands

```bash
.venv/bin/ratecard validate                      # taxonomy invariants
.venv/bin/ratecard match data/corpus/phase00.csv # run the matcher
.venv/bin/ratecard label data/eval/labels.csv    # <- the blocking task
.venv/bin/ratecard evaluate data/eval/labels.csv
python scripts/phase00_seed_corpus.py --fetch    # rebuild the corpus
.venv/bin/python -m pytest tests/ -q && .venv/bin/ruff check src tests scripts
```

Phase 01 runs on stdlib + PyYAML alone. Heavier stages are optional extras.
Install torch from the **CPU index** — there is no NVIDIA card on this machine
and the default wheel drags in ~3GB of unused CUDA.

## Rules that must not be broken

- **Do not tune any threshold in `normalise/matcher.py` before Phase 03 labels
  exist.** They are untuned placeholders on purpose. Fitting them to the corpus
  first makes the evaluation meaningless. This is the single most important
  constraint in the project.
- **Do not read the `holdout` split** until every threshold is frozen. It is
  meant to be looked at once. `ratecard evaluate` defaults to `train`.
- **Do not re-draw the evaluation sample if any row is labelled.** Regenerating
  is cheap; re-labelling 500 rows by hand is not. Check first.
- **Only an exact alias hit skips review.** Everything else carries
  `needs_review`, however high it scored.
- **Never quote sample rates as corpus rates.** The evaluation sample is
  stratified; `corpus_estimate` reweights by the sizes in
  `data/eval/labels.csv.population.json`.

## Settled — do not re-litigate

- **OCR is a fallback**, not the headline. The census found text layers.
- **A price is not a scalar.** Column 1 (`OPD`, walk-in) is the comparison tier.
  The two Narayana units use *different* tier schemas — 11 columns in Bengaluru,
  8 in Guwahati — so `price_tier` cannot be a shared enum across publishers.
- **Guwahati prices are not Bengaluru prices.** That file is name-harvesting
  only and carries `display_ok=False`. The Bengaluru unit is Mazumdar Shaw.
- **Search-first, not a feed.** Not an emergency tool. The claim is fixing
  *price opacity*, not "improving healthcare access".
- **Cut and staying cut:** price prediction, appointment booking, blockchain
  review ledger, real-time booking sync, price-lock guarantee.
- **The rerank is a precision filter, not a recall booster**, and is off by
  default. Over 1,500 names it refused 204 lexical matches and added 11.

## Traps this codebase has already hit

Every one of these has a regression test in `tests/test_regressions.py`.

- **Single letters are identity.** `"a"` was a stopword; `"Vitamin A"` became
  `"vitamin"`, and a bare `VITAMIN` row exact-matched Vitamin A at confidence
  1.0. Never let the stopword list eat a letter.
- **`token_set_ratio` returns a flat 100 for any subset.** It generates
  candidates; `WRatio` ranks them. Do not collapse them back into one scorer.
- **"CT" means Clotting Time** at least as often as computed tomography. The
  attribute extractor only reads it as a scan next to a region word.
- **Generic words are not evidence.** `12 GENE PANEL (NGS)` tied `iron_studies`
  against `lipid_profile` because all three contain "panel".
- **`distinct_from` is resolved by evidence**, not by a wider margin — a word in
  the raw name belonging to one of the pair and not the other. Widening the
  margin instead wrongly abstains on `BLOOD UREA NITROGEN (BUN)`.
- **PDF rows wrap.** Long names push the price run onto the next line; the
  parser rejoins them. It also reports what it still cannot parse rather than
  dropping it silently — that bug cost 16% of one source.
- **The corpus is a whole hospital catalogue**, not a lab menu: surgeries,
  chemotherapy, bed charges. Low coverage is expected and correct; ~59% of names
  have no answer in a 210-test routine taxonomy.

## Known-unfinished

- **LOINC codes are unverified** — seeded from model memory, not a fetched
  LOINC release. Check against loinc.org before Phase 03 and null anything that
  does not map cleanly. Imaging deliberately carries none.
- **31 Guwahati rows still fail to parse** (merged double-records). Reported in
  the script's output, not hidden.
- Repo is named `hopital_project` (typo, and the old "price prediction" framing).
  Worth renaming.

## Layout

```
src/ratecard/
  names.py           normalisation, shared by taxonomy and matcher
  taxonomy/          210 tests in data/*.yaml, loader validates hard
  normalise/         rules.py (veto) attributes.py (raw-string bridge)
                     matcher.py (4 layers) rerank.py (optional, lazy)
  evaluate/          sampling.py metrics.py labelling.py
scripts/             phase00_seed_corpus.py — throwaway, replaced by Phase 04
data/raw|interim|corpus/   gitignored, regenerable
data/eval/                 COMMITTED — irreplaceable hand labels
```
