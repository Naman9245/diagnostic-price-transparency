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
| 00 Seed corpus | superseded by Phase 04 — `ratecard ingest` now builds it |
| 01 Taxonomy | done — 210 canonical tests, validating |
| 02 Matcher | built, **untuned** — 20.7% of rows resolved, 205/210 tests observed |
| 03 Label & evaluate | **train labelled (345/345, by Claude)**; holdout 0/155. Learned acceptor trained on train (`ratecard train`); unconfirmed on holdout |
| 04 Pipeline | Stages 1-3 done — `ratecard ingest --fetch` builds ~13,000 rows from 5 registry sources (13,063 on 2026-09-27; sitemaps drift). Only **1 source is displayable**, which is the real gap |
| 05 | Database & Stage 5 loader — schema in `supabase/migrations/`, `ratecard load` (dry run: 111 public rows, 106 tests). Tested offline; **not yet applied to a live database** |
| 06 | not started — patient PWA: price search (`web/`, Next.js) |
| 07 | not started — partner dashboard + fictional demo hospitals |
| 08 | not started — register once, book, live queue (Supabase Auth + Realtime) |
| 09 | not started — payments, Razorpay **test mode only** |
| 10 | not started — ABHA via the ABDM sandbox, behind an adapter |

Phase 03 is the deliverable for the price side. Phases 07-10 are the partner
side: booking exists only for providers who sign up — see `docs/product.md`.

## Commands

```bash
.venv/bin/ratecard validate                      # taxonomy invariants
.venv/bin/ratecard match data/corpus/phase00.csv # run the matcher
.venv/bin/ratecard label data/eval/labels.csv    # <- the blocking task
.venv/bin/ratecard evaluate data/eval/labels.csv
.venv/bin/ratecard train                         # fit the learned acceptor (train split only)
.venv/bin/ratecard match data/corpus/phase00.csv --learned
.venv/bin/ratecard ingest --fetch                # stages 1-3, rebuild the corpus
.venv/bin/ratecard load --dry-run                 # stage 5: what would be written / public
.venv/bin/python -m pytest tests/ -q && .venv/bin/ruff check src tests scripts
```

Phase 01 runs on stdlib + PyYAML alone, and that is enforced, not just
documented: `validate`, `stats`, `lookup`, `check` and `hard-negatives` must
keep working with nothing else installed. The matcher is imported lazily to
keep it true — do not hoist `from ratecard.normalise.matcher import ...` to
module scope in `cli.py` or `evaluate/sampling.py`.

Install torch from the **CPU index** — there is no NVIDIA card on this machine
and the default wheel drags in ~3GB of unused CUDA.

`AGENTS.md` is a symlink to this file. Edit this one.

## Phase 03 findings (train split, model-labelled)

The 345 train rows were labelled by Claude at the user's request,
`labelled_by=claude`, working from raw name + unranked candidates + taxonomy
only - matcher guess, method, confidence and stratum were hidden. Model labels
are weaker ground truth than human ones; any write-up must say so. A human
audit of a random ~50 would give an agreement figure.

- **Exact alias hits: 100% precision** (n=42). The aliases are right.
- **Lexical commits: 11.5% precision** (n=96). Badly overconfident.
- **Every one of the 85 wrong matches is overreach, zero are confusion.** The
  matcher never picked the wrong canonical test when a right one existed. It
  fails only by matching out-of-taxonomy names - "HIV 1 viral load" to the
  antibody screen, "t3 reverse" to total T3, a progesterone-receptor
  immunostain to serum progesterone.
- **Hard-negative accuracy 91.4% [84-96]**, n=93. The veto machinery works.
- **All 8 misses are thin-margin abstentions** with the answer in the top two.

So tuning is two separate knobs, not one threshold: stop overreach on names
with substantial unmatched content, and loosen thin-margin slightly.

**Learned acceptor (2026-09-23).** Rather than hand-tune those knobs, a logistic
regression over 15 pair features replaces `ACCEPT_THRESHOLD` and `MARGIN`
(`src/ratecard/learn/`). Out-of-fold on the 293 non-exact train names:

| | precision | recall | overreach |
|---|---|---|---|
| rule-based | 11.5% [7-19] | 57.9% | 85 |
| learned | 87.5% [64-97] | 73.7% | 2 |

It beats the rule-based matcher on precision *and* recall. The two strongest
reject signals are raw words the candidate does not cover and words absent
from the whole taxonomy vocabulary - exactly the overreach cases. Opt-in via
`match --learned`; the fixed thresholds remain the default until the holdout
confirms it. Only 19 positive pairs, so treat the numbers as provisional.

Recall was mis-reported as 36.3% until this date. `wrong_match` held both
overreach and confusion and the denominator counted both; recall asks only
about names that have a real answer. True train recall is 86.9%. A test had
been asserting the buggy value.

## Rules that must not be broken

- **Do not tune any threshold in `normalise/matcher.py` before Phase 03 labels
  exist.** They are untuned placeholders on purpose. Fitting them to the corpus
  first makes the evaluation meaningless. This is the single most important
  constraint in the project.
- **Do not read the `holdout` split** until every threshold is frozen. It is
  meant to be looked at once. `ratecard evaluate` defaults to `train`. The
  train split is now labelled; the holdout is not, and whoever labels it
  should ideally not be whoever tunes the thresholds.
- **Do not re-draw the evaluation sample if any row is labelled.** Regenerating
  is cheap; re-labelling 500 rows by hand is not. Check first.
- **Only an exact alias hit skips review.** Everything else carries
  `needs_review`, however high it scored.
- **Adding a source of a known format is a YAML entry, not a code change.**
  Adapters are dispatched by the registry's `parser` field. If you find
  yourself editing `parse/` to add a source, check the format is really new.
- **A source with `display_ok: false` may never have a price shown.** Names
  may be harvested. The registry refuses `display_ok: true` without a city,
  because the census published Guwahati prices as Bengaluru ones.
- **Only `display_ok` and not-`needs_review` rows are public.** Today that
  means exact alias hits from one source. The learned acceptor's matches stay
  out of public view until the holdout confirms it.
- **Demo providers are fictional and badged "Demo" everywhere.** Never seed a
  real hospital's name as a partner, and never give a demo provider a price
  that could be mistaken for a real one — its prices come from a `demo_seed`
  source.
- **ABDM and Razorpay identifiers come from their official docs**, never from
  memory — the LOINC episode below is why. Test keys only, in `.env.local`,
  never committed.
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
- **Cut and staying cut:** price prediction, blockchain review ledger,
  real-time sync with a hospital's own HMIS, price-lock guarantee.
- **Booking is partner-only** (reversed 2026-09-27; it was cut). A provider
  whose `partner_status` is `none` never gets a Book button, and the database
  refuses the insert — RLS, not just the UI.
- **Runtime is Supabase + Next.js, no FastAPI.** Search is SQL (PostGIS,
  pg_trgm) over exact aliases; the fuzzy matcher never runs at query time. Python
  stays a batch pipeline.
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
- **A sitemap index is not always a `<sitemapindex>`.** Redcliffe publishes
  its index as a `<urlset>` with child sitemaps listed among ordinary nav URLs.
  Detecting on the wrapper element harvested 24 names instead of 2,215; detect
  on `<loc>` values ending `.xml` instead, and drop the index once children are
  found or its nav pages become test names.
- **Sitemap URLs carry query strings and percent-encoding.**
  `pathology-test/hba1c?q=hba1c` and `urine%20routine`. Strip the query and
  unquote before taking the slug — the throwaway baked both into the name.
- **PDF rows wrap.** Long names push the price run onto the next line; the
  parser rejoins them. It also reports what it still cannot parse rather than
  dropping it silently — that bug cost 16% of one source.
- **The corpus is a whole hospital catalogue**, not a lab menu: surgeries,
  chemotherapy, bed charges. Low coverage is expected and correct; ~59% of names
  have no answer in a 210-test routine taxonomy.
- **Optional deps must stay optional.** `cli.py` imported `Matcher` at module
  scope, so `ratecard validate` died with `ModuleNotFoundError: rapidfuzz` on
  every clean install, breaking a promise the README makes. Tested in a
  subprocess with the import blocked.
- **A Windows pipe is cp1252.** `ratecard validate > out.txt` died on the ✓;
  the console hid it because Python writes UTF-8 there. `main()` now switches
  non-UTF-8 stdio to UTF-8. `PYTHONIOENCODING=cp1252` reproduces it on any OS.
- **A model-recalled identifier is probably wrong.** Of 147 LOINC codes seeded
  from memory, 12 did not exist and 2 pointed at the wrong analyte — `ace` was
  Biopterin in 24-hour urine, and the two Coombs codes were on each other's
  tests. Most fabrications were *one digit off* a real code (`38476-0` for
  `38476-8`), which is exactly the shape that survives a plausibility check.
  Never hand-write an external identifier; look it up.
- **A test can guard a bug.** `test_precision_recall_and_coverage` asserted
  recall = 1/3, which was the buggy value. Tests encode what someone believed
  when they wrote them; when a definition is wrong, its test is wrong too.
- **A docstring is not a guarantee.** Twice now a docstring has described
  behaviour the code did not have — `_apply_vetoes` claimed to use
  `distinct_from` and never did, and `fetch_raw` claimed never to overwrite in
  place while `--force` did exactly that. When one says something load-bearing,
  check the code does it.

## Known-unfinished

- ~~LOINC codes are unverified~~ **done 2026-09-13.** All 145 checked against
  the NLM Clinical Table Search Service (free, no licence key, unlike
  fhir.loinc.org). 14 were wrong and are fixed, 2 nulled. Re-check with
  `python scripts/verify_loinc.py` — a clean run reports 0 and 0. Imaging
  deliberately carries none.
- One dud row in the evaluation sample: `madurai`, a city landing page that
  leaked in before the extraction filtered them. Label it `none`.
- **31 Guwahati rows still fail to parse** (merged double-records). Reported in
  the script's output, not hidden.
- The GitHub remote is `Naman9245/diagnostic-price-transparency`, private.
  It is also cloned at `Documents/hospital` on the Windows machine, where the
  venv lives at `.venv/Scripts/`, not `.venv/bin/`.

## Layout

```
src/ratecard/
  names.py           normalisation, shared by taxonomy and matcher
  taxonomy/          210 tests in data/*.yaml, loader validates hard
  normalise/         rules.py (veto) attributes.py (raw-string bridge)
                     matcher.py (4 layers) rerank.py (optional, lazy)
  evaluate/          sampling.py metrics.py labelling.py
  learn/             features.py dataset.py model.py - the learned acceptor
  registry/          Stage 1 — sources in data/sources.yaml, validated hard
  fetch/             Stage 2 — immutable raw store, hash-pinned
  parse/             Stage 3 — adapters dispatched by the registry's `parser`
  pipeline.py        stages 1-3 wired: registry -> fetch -> parse -> rows
  load/              Stage 5 — build.py (pure, holds the public rules) db.py (psycopg)
                     data/providers.yaml: who charges each displayable source, looked-up coords
supabase/migrations/ price side + partner side; booking and queue are SQL functions
scripts/             verify_loinc.py — re-check codes against the NLM table
prototype/           standalone demo (FastAPI + Flutter + Vue) on fictional mock data, teal/mint UI.
                     Not the runtime and not wired to the pipeline; see prototype/README.md
data/raw|interim|corpus/   gitignored, regenerable
data/eval/                 COMMITTED — irreplaceable labels
data/models/acceptor.json  COMMITTED — trained model, plain JSON
```
