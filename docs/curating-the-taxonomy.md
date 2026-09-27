# Curating the taxonomy

## Adding a test

Append to the right file in `src/ratecard/taxonomy/data/`. Minimum viable entry:

```yaml
- id: serum_ldh                # lowercase snake_case, permanent
  name: Lactate Dehydrogenase  # the canonical display name
  category: clinical_chemistry
  kind: lab                    # lab | imaging
  specimen: serum              # lab only, required
  fasting_required: false
  loinc: "2532-0"              # omit rather than guess
  aliases: [LDH, lactate dehydrogenase, serum LDH]
```

Run `ratecard validate` before committing. It fails on: duplicate ids, duplicate
names, alias collisions across tests, dangling component or `distinct_from`
references, panels without analytes, lab tests without a specimen, imaging
studies without a modality, and `views`/`contrast` set on modalities where they
are meaningless.

## Writing aliases

Aliases are the highest-value field in the file. Write how the *sources* write
it, not how a textbook does. Draw from the corpus, not from memory.

Include: the abbreviation (`TLC`), the expansion (`total leukocyte count`), the
abbreviation-with-expansion form the PDFs love (`total leukocyte count (TLC)`),
Indian vernacular (`sugar F`, `haemogram`, `CUE`), and both British and American
spellings where the normaliser does not already fold them.

Do **not** add an alias that could belong to two tests. `ratecard validate`
rejects it, and that rejection is the point: an ambiguous surface form should
make the matcher abstain, not guess. `lipid profile complete` is left unaliased
for exactly this reason — its analyte list differs per source.

## Panels

`is_panel: true` requires `analytes`. List every reported analyte, because
analyte count and analyte set are what separate `lipid_profile` from
`lipid_profile_extended` and `thyroid_profile` from `thyroid_profile_free`.

`components` is narrower: only sub-tests that are canonical entries in their own
right, i.e. separately orderable and separately priced.

## distinct_from

Use it only when no structural field separates the pair. If they differ by
specimen, panel size, modality, views or contrast, the rule layer already
handles it and a declaration adds noise.

Every declaration is automatically a seed for the Phase 03 hard-negative
evaluation set (`ratecard hard-negatives`), so writing one is also writing a
test case.

## Adding a specialty

Specialties live in one file, `src/ratecard/specialties/data/specialties.yaml`,
separate from the tests. Minimum viable entry:

```yaml
- id: rheumatology              # lowercase snake_case, permanent
  name: Rheumatology            # the department, in Indian English spelling
  practitioner: Rheumatologist  # what the doctor is called
  category: medical             # medical | surgical | dental | allied_health
  aliases: [rheumatology, rheumatologist]
  related_terms: [arthritis, gout]
```

**Aliases** name this specialty and nothing else, exactly as for tests. Write
both spellings where `names.normalise` does not fold them: it folds
`paediatric`, `gynaecology` and `haematology`, but not `paediatrician`,
`orthopaedics` or `gynaecologist`. Department words (`department`, `dept`,
`OPD`, `clinic`, `consultation`, `consultant`, `unit`, `services`) are stripped
before lookup, so "Department of Rheumatology" needs no alias of its own.

**Related terms** are what a patient types that points here without naming it:
a body part, a named condition, or an umbrella word. They may be shared, and
they only ever suggest. If a word could name two specialties, it belongs here
and not in aliases: "kidney specialist" is a related term on both nephrology and
urology. Leave symptoms out; turning "chest pain" into a specialty is triage.

**`distinct_from`** marks a pair patients confuse that is never the same:
cardiology and cardiothoracic surgery, psychiatry and clinical psychology,
physical medicine and physiotherapy. `tests/test_specialties.py` pins the
common confusions; add a case when you add a trap.

`ratecard validate` fails on duplicate ids or names, alias collisions, a related
term that is also an alias, an alias made only of department words, and
dangling `distinct_from` references. `ratecard specialty "some name"` shows what
a name resolves to, or what it suggests.
