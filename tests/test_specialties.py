"""The specialty list is hand-written, so its invariants are the safety net.

Most of these tests pin a confusion patients really make: a cardiologist is not
a cardiac surgeon, a physiatrist is not a physiotherapist, and "kidney doctor"
does not say which of two specialists is meant.
"""

import pytest

from ratecard.specialties import Category, SpecialtyError, load, specialty_key


@pytest.fixture(scope="module")
def specialties():
    return load()


def test_the_list_loads_and_validates(specialties):
    assert len(specialties) >= 35
    assert {s.category for s in specialties} == set(Category)


def test_every_surface_form_resolves_to_its_own_specialty(specialties):
    for s in specialties:
        for surface in (s.name, s.practitioner, *s.aliases):
            assert specialties.lookup(surface) is s, f"{surface!r} did not resolve to {s.id}"


def test_no_related_term_ever_resolves(specialties):
    """A related term suggests. If it resolved, "kidney" would quietly pick one
    specialty while the search claimed to offer a choice."""
    for s in specialties:
        for term in s.related_terms:
            assert specialties.lookup(term) is None, f"{term!r} resolves, but is a related term"
            assert s in specialties.suggest(term)


@pytest.mark.parametrize("a, b", [
    ("paediatrician", "pediatrician"),
    ("paediatrics", "pediatrics"),
    ("orthopaedics", "orthopedics"),
    ("orthopaedic surgeon", "orthopedic surgeon"),
    ("gynaecologist", "gynecologist"),
    ("haematologist", "hematologist"),
    ("paediatric surgeon", "pediatric surgeon"),
    ("clinical haematology", "clinical hematology"),
])
def test_british_and_american_spellings_resolve_alike(specialties, a, b):
    assert specialties.lookup(a) is not None
    assert specialties.lookup(a) is specialties.lookup(b)


@pytest.mark.parametrize("raw, expected", [
    ("Department of Cardiology", "cardiology"),
    ("CARDIOLOGY OPD", "cardiology"),
    ("Dept. of Orthopaedics", "orthopaedics"),
    ("Consultant Physician", "general_medicine"),
    ("ENT Clinic", "ent"),
    ("Obs & Gynae", "obstetrics_gynaecology"),
    ("OB/GYN", "obstetrics_gynaecology"),
    ("PM&R", "physical_medicine_rehabilitation"),
    ("Dermatology, Venereology & Leprosy", "dermatology"),
    ("TB & Chest", "pulmonology"),
    ("CTVS", "cardiothoracic_surgery"),
    ("skin doctor", "dermatology"),
    ("Opthalmology", "ophthalmology"),
])
def test_how_hospitals_and_patients_write_it(specialties, raw, expected):
    found = specialties.lookup(raw)
    assert found is not None and found.id == expected


@pytest.mark.parametrize("a, b", [
    ("cardiologist", "cardiac surgeon"),
    ("neurologist", "neurosurgeon"),
    ("nephrologist", "urologist"),
    ("psychiatrist", "psychologist"),
    ("physiatrist", "physiotherapist"),
    ("physical medicine and rehabilitation", "physical therapy"),
    ("paediatrician", "paediatric surgeon"),
    ("child specialist", "child surgeon"),
    ("gastroenterologist", "GI surgeon"),
    ("medical oncologist", "surgical oncologist"),
    ("dental surgeon", "oral surgeon"),
    ("endocrinologist", "diabetologist"),
])
def test_the_confusions_stay_apart(specialties, a, b):
    left, right = specialties.lookup(a), specialties.lookup(b)
    assert left is not None and right is not None
    assert left is not right


def test_distinct_from_pairs_never_share_a_surface_form(specialties):
    for s in specialties:
        for other_id in s.distinct_from:
            other = specialties[other_id]
            mine = {specialty_key(x) for x in (s.name, s.practitioner, *s.aliases)}
            theirs = {specialty_key(x) for x in (other.name, other.practitioner, *other.aliases)}
            assert not mine & theirs


@pytest.mark.parametrize("raw, expected", [
    ("kidney doctor", {"nephrology", "urology"}),
    ("kidney specialist", {"nephrology", "urology"}),
    ("oncologist", {"medical_oncology", "surgical_oncology", "radiation_oncology"}),
    ("ortho", {"orthopaedics", "orthodontics"}),
    ("neuro", {"neurology", "neurosurgery"}),
    ("gastro", {"gastroenterology", "surgical_gastroenterology"}),
    ("mental health", {"psychiatry", "clinical_psychology"}),
    ("heart", {"cardiology", "cardiothoracic_surgery"}),
])
def test_an_ambiguous_word_suggests_every_reading_and_resolves_to_none(specialties, raw,
                                                                       expected):
    assert specialties.lookup(raw) is None
    assert {s.id for s in specialties.suggest(raw)} == expected


@pytest.mark.parametrize("raw", ["GP", "general practitioner", "cardiac sciences",
                                 "cosmetology", "laparoscopic surgery", "OPD"])
def test_deliberately_unresolved(specialties, raw):
    """Each of these names more than one thing in India; see the YAML notes."""
    assert specialties.lookup(raw) is None


def test_suggestions_match_whole_words_only(specialties):
    """"ear" is a related term for ENT; the word "early" must not trip it."""
    assert "ent" not in {s.id for s in specialties.suggest("early pregnancy")}


def test_department_words_are_stripped_but_identity_words_are_not():
    assert specialty_key("Department of Cardiology") == "cardiology"
    assert specialty_key("skin doctor") == "skin doctor"
    assert specialty_key("heart specialist") == "heart specialist"


# --- the validator refuses what would make search guess ----------------------

GOOD = """
- id: cardiology
  name: Cardiology
  practitioner: Cardiologist
  category: medical
  aliases: [heart specialist]
  related_terms: [heart]
- id: cardiothoracic_surgery
  name: Cardiothoracic Surgery
  practitioner: Cardiac Surgeon
  category: surgical
  aliases: [CTVS]
  related_terms: [heart]
"""


def _load(tmp_path, text):
    path = tmp_path / "specialties.yaml"
    path.write_text(text, encoding="utf-8")
    return load(path)


def _problems(tmp_path, text):
    with pytest.raises(SpecialtyError) as exc:
        _load(tmp_path, text)
    return exc.value.problems


def test_a_shared_related_term_is_allowed(tmp_path):
    loaded = _load(tmp_path, GOOD)
    assert loaded.term_index["heart"] == ("cardiology", "cardiothoracic_surgery")


def test_an_alias_two_specialties_share_is_refused(tmp_path):
    problems = _problems(tmp_path, GOOD.replace("[CTVS]", "[CTVS, heart specialist]"))
    assert any("alias collision on 'heart specialist'" in p for p in problems)


def test_a_related_term_that_is_also_an_alias_is_refused(tmp_path):
    problems = _problems(tmp_path, GOOD.replace("[CTVS]", "[CTVS, heart]"))
    assert any("related term 'heart' is also an alias" in p for p in problems)


def test_an_alias_of_only_department_words_is_refused(tmp_path):
    problems = _problems(tmp_path, GOOD.replace("[CTVS]", "[CTVS, OPD]"))
    assert any("normalises to an empty string" in p for p in problems)


@pytest.mark.parametrize("edit, message", [
    (("category: surgical", "category: surgery"), "'surgery' is not a valid Category"),
    (("  related_terms: [heart]\n- id: cardiothoracic",
      "  distinct_from: [cardiothoracic]\n  related_terms: [heart]\n- id: cardiothoracic"),
     "distinct_from 'cardiothoracic' is not a specialty id"),
    (("id: cardiothoracic_surgery", "id: cardiology"), "duplicate id 'cardiology'"),
    (("  practitioner: Cardiac Surgeon\n", ""), "missing required field 'practitioner'"),
])
def test_malformed_entries_are_refused(tmp_path, edit, message):
    problems = _problems(tmp_path, GOOD.replace(*edit, 1))
    assert any(message in p for p in problems), problems
