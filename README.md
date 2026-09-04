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
| 00 Seed corpus | done 2 Sep | 6,766 raw names, 3 sources — **output not on disk, see below** |
| 01 Canonical taxonomy | in progress | 191 tests, validating, exit criterion unmeasured |
| 02 The matcher | not started | |
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

`src/ratecard/` mirrors those stages one directory each. Only `taxonomy/`,
`names.py` and `normalise/rules.py` carry implementation today.

## Phase 01: the taxonomy

`src/ratecard/taxonomy/data/*.yaml` — 191 hand-curated canonical tests across
14 categories, 996 aliases, 977 indexed surface forms.

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

## Two things that are not done

**The Phase 00 corpus is not on disk.** The 6,766-name CSV that Phase 01's exit
criterion measures against does not exist in this repo or anywhere on the
machine — the same way the original census fetches were not kept. `ratecard
coverage` is written and tested but has nothing to run against, so the "80% of
the corpus by row volume" criterion is currently **unmeasured**, not passed.
Re-running the Phase 00 dump is the next blocking task.

**LOINC codes are unverified.** 135 of 159 lab tests carry a code, seeded from
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
