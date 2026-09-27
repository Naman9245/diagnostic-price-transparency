"""The migrations, applied to a real Postgres.

Opt-in, because it needs a server. Point RATECARD_TEST_DATABASE_URL at a
superuser connection on a Postgres with PostGIS and pg_trgm installed:

    RATECARD_TEST_DATABASE_URL=postgresql://user:pass@localhost/postgres \\
        python -m pytest tests/test_database.py

Each run creates a throwaway database, applies a stand-in for the few parts of
Supabase the migrations use (the auth schema, auth.uid(), the anon and
authenticated roles and their default grants), then every file in
supabase/migrations/ in order, loads the reference data through the real
Stage 5 writer, and drops the database afterwards.
"""

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

DSN = os.environ.get("RATECARD_TEST_DATABASE_URL")
if not DSN:
    pytest.skip("set RATECARD_TEST_DATABASE_URL to run the database tests",
                allow_module_level=True)
psycopg = pytest.importorskip("psycopg")

from psycopg import errors, sql
from psycopg.conninfo import make_conninfo

from ratecard.load import (
    PriceBatch,
    alias_records,
    canonical_test_records,
    load_providers,
    source_records,
    specialty_alias_records,
    specialty_records,
    specialty_term_records,
)
from ratecard.load.db import write
from ratecard.registry import load as load_registry
from ratecard.specialties import load as load_specialties
from ratecard.taxonomy import load as load_taxonomy

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"

# What Supabase provides before any migration runs, and nothing more.
SUPABASE_STANDIN = """
create schema extensions;
create schema auth;
create table auth.users (id uuid primary key default gen_random_uuid());
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end $$;
grant usage on schema public, extensions, auth to anon, authenticated;
alter default privileges in schema public
  grant select, insert, update, delete on tables to anon, authenticated;
alter default privileges in schema public
  grant usage, select on sequences to anon, authenticated;
"""


@pytest.fixture(scope="module")
def db():
    name = f"ratecard_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=name), autocommit=True) as conn:
            conn.execute(SUPABASE_STANDIN)
            for path in sorted(MIGRATIONS.glob("*.sql")):
                conn.execute(path.read_text(encoding="utf-8"))
            _load_reference_data(conn)
            yield conn
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(sql.SQL("drop database if exists {} with (force)")
                          .format(sql.Identifier(name)))


def _load_reference_data(conn):
    taxonomy, specialties, registry = load_taxonomy(), load_specialties(), load_registry()
    providers = load_providers(registry)
    write(conn, canonical_test_records(taxonomy), alias_records(taxonomy), providers,
          source_records(registry, providers), PriceBatch(),
          specialties=specialty_records(specialties),
          specialty_aliases=specialty_alias_records(specialties),
          specialty_terms=specialty_term_records(specialties))


@contextmanager
def as_anon(conn):
    """What the public web app sees: row-level security applies."""
    conn.execute("set role anon")
    try:
        yield
    finally:
        conn.execute("reset role")


def _search(conn, q):
    with as_anon(conn):
        return conn.execute("select id, via, score from public.search_specialties(%s)",
                            (q,)).fetchall()


def test_the_writer_loads_every_specialty(db):
    specialties = load_specialties()
    count = db.execute("select count(*) from public.specialty").fetchone()[0]
    aliases = db.execute("select count(*) from public.specialty_alias").fetchone()[0]
    assert (count, aliases) == (len(specialties), len(specialties.alias_index))


def test_writing_twice_converges(db):
    before = db.execute("select count(*) from public.specialty_term").fetchone()[0]
    _load_reference_data(db)
    after = db.execute("select count(*) from public.specialty_term").fetchone()[0]
    assert before == after > 0


def test_a_name_resolves_first(db):
    hits = _search(db, "skin doctor")
    assert hits[0][:2] == ("dermatology", "alias")
    assert hits[0][2] == pytest.approx(1.0)


def test_an_ambiguous_word_comes_back_as_a_choice(db):
    hits = {row[0]: row[1] for row in _search(db, "kidney")}
    assert hits["nephrology"] == hits["urology"] == "term"


def test_partial_typing_autocompletes(db):
    assert "cardiology" in {row[0] for row in _search(db, "cardio")}


def test_a_doctor_cannot_have_a_free_text_specialty(db):
    provider = db.execute("select id from public.provider limit 1").fetchone()[0]
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        db.execute("insert into public.doctor (provider_id, name, specialty_id, fee_inr) "
                   "values (%s, 'Dr Test', 'heart stuff', 500)", (provider,))
    with pytest.raises(errors.UndefinedColumn), db.transaction():
        db.execute("insert into public.doctor (provider_id, name, specialty, fee_inr) "
                   "values (%s, 'Dr Test', 'Cardiology', 500)", (provider,))


@pytest.fixture(scope="module")
def clinic(db):
    """A demo partner with two cardiologists and a neurologist, plus a doctor
    at the real, non-partner hospital the loader created."""
    real_id, lat, lng = db.execute(
        "select id, extensions.st_y(geom::extensions.geometry), "
        "extensions.st_x(geom::extensions.geometry) from public.provider "
        "where partner_status = 'none' limit 1").fetchone()
    demo_id = db.execute(
        "insert into public.provider (slug, name, kind, city, geom, partner_status) "
        "values ('demo-test', 'Demo Test Clinic', 'clinic', 'Bengaluru', "
        "extensions.st_setsrid(extensions.st_makepoint(%s, %s), 4326)::extensions.geography, "
        "'demo') returning id", (lng + 0.01, lat)).fetchone()[0]

    def doctor(provider, name, specialty, fee):
        return db.execute(
            "insert into public.doctor (provider_id, name, specialty_id, fee_inr) "
            "values (%s, %s, %s, %s) returning id", (provider, name, specialty, fee)
        ).fetchone()[0]

    cheap = doctor(demo_id, "Dr Cheap", "cardiology", 400)
    dear = doctor(demo_id, "Dr Dear", "cardiology", 900)
    doctor(demo_id, "Dr Neuro", "neurology", 300)
    doctor(real_id, "Dr Not A Partner", "cardiology", 100)
    db.execute(
        "insert into public.schedule_rule (doctor_id, weekday, starts, ends, slot_minutes) "
        "values (%s, extract(dow from now() at time zone 'Asia/Kolkata'), "
        "'09:00', '13:00', 15)", (cheap,))
    return {"lat": lat, "lng": lng, "cheap": cheap, "dear": dear}


def _near(db, clinic, specialty="cardiology"):
    with as_anon(db):
        return db.execute(
            "select doctor_name, fee_inr, partner_status, hours_today, today_state "
            "from public.doctors_near(%s, %s, %s)",
            (specialty, clinic["lat"], clinic["lng"])).fetchall()


def test_doctors_near_lists_partners_cheapest_first(db, clinic):
    rows = _near(db, clinic)
    assert [(r[0], r[1]) for r in rows] == [("Dr Cheap", 400), ("Dr Dear", 900)]
    assert all(r[2] == "demo" for r in rows), "the UI badges these Demo"


def test_a_non_partner_hospital_never_lists_doctors(db, clinic):
    """Its ₹100 doctor would sort first, if the rule leaked."""
    assert "Dr Not A Partner" not in {r[0] for r in _near(db, clinic)}


def test_only_the_asked_specialty_is_listed(db, clinic):
    assert [r[0] for r in _near(db, clinic, "neurology")] == ["Dr Neuro"]


def test_todays_hours_and_status_are_shown_and_unknown_stays_unknown(db, clinic):
    rows = {r[0]: r for r in _near(db, clinic)}
    assert rows["Dr Cheap"][3] == "09:00-13:00"
    assert rows["Dr Dear"][3] is None, "no schedule today"
    assert rows["Dr Cheap"][4] is None, "nobody has set today's status yet"

    db.execute("insert into public.doctor_day_status (doctor_id, day, state) "
               "values (%s, (now() at time zone 'Asia/Kolkata')::date, 'in_opd')",
               (clinic["cheap"],))
    assert {r[0]: r[4] for r in _near(db, clinic)}["Dr Cheap"] == "in_opd"
