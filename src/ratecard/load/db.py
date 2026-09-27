"""Stage 5, the half that touches Postgres.

Writes exactly what `build` produced, in one transaction, and decides nothing.
Re-running it is safe: reference data is upserted, and each source's price
observations are replaced wholesale, so a reload after a re-fetch or a taxonomy
change converges instead of accumulating.

psycopg is imported by the caller (`ratecard load`), lazily, so the stdlib +
PyYAML commands keep working without it.
"""

from __future__ import annotations

from typing import Any

from ratecard.load.build import PriceBatch, Provider


def write(conn: Any, tests: list[dict[str, Any]], aliases: list[tuple[str, str]],
          providers: list[Provider], sources: list[dict[str, Any]],
          prices: PriceBatch, *, specialties: list[dict[str, Any]],
          specialty_aliases: list[tuple[str, str]],
          specialty_terms: list[tuple[str, str]]) -> dict[str, int]:
    """Load everything inside the caller's connection, as one transaction.

    The specialty arguments are keyword-only and required: their aliases and
    terms are replaced wholesale, so a caller that forgot them would silently
    empty specialty search rather than leave it alone.
    """
    counts: dict[str, int] = {}
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """insert into public.canonical_test
                 (id, name, category, kind, loinc_code, specimen, is_panel)
               values (%(id)s, %(name)s, %(category)s, %(kind)s, %(loinc_code)s,
                       %(specimen)s, %(is_panel)s)
               on conflict (id) do update set
                 name = excluded.name, category = excluded.category, kind = excluded.kind,
                 loinc_code = excluded.loinc_code, specimen = excluded.specimen,
                 is_panel = excluded.is_panel""",
            tests,
        )
        counts["canonical_test"] = len(tests)

        # Aliases are derived data: replace them, so a surface form removed from
        # the taxonomy stops resolving.
        cur.execute("delete from public.test_alias")
        with cur.copy("copy public.test_alias (surface, canonical_test_id) from stdin") as copy:
            for surface, test_id in aliases:
                copy.write_row((surface, test_id))
        counts["test_alias"] = len(aliases)

        # Upserted, never deleted: a doctor row may point at a specialty, and
        # the foreign key should refuse a removal rather than cascade it.
        cur.executemany(
            """insert into public.specialty (id, name, practitioner, category)
               values (%(id)s, %(name)s, %(practitioner)s, %(category)s)
               on conflict (id) do update set
                 name = excluded.name, practitioner = excluded.practitioner,
                 category = excluded.category""",
            specialties,
        )
        counts["specialty"] = len(specialties)

        cur.execute("delete from public.specialty_alias")
        with cur.copy("copy public.specialty_alias (surface, specialty_id) from stdin") as copy:
            for surface, specialty_id in specialty_aliases:
                copy.write_row((surface, specialty_id))
        counts["specialty_alias"] = len(specialty_aliases)

        cur.execute("delete from public.specialty_term")
        with cur.copy("copy public.specialty_term (term, specialty_id) from stdin") as copy:
            for term, specialty_id in specialty_terms:
                copy.write_row((term, specialty_id))
        counts["specialty_term"] = len(specialty_terms)

        # partner_status is deliberately not in the update list: whether a real
        # provider has signed up is not the pipeline's business.
        provider_ids: dict[str, int] = {}
        for p in providers:
            cur.execute(
                """insert into public.provider
                     (slug, name, brand, kind, city, locality, address, phone, geom)
                   values (%s, %s, %s, %s, %s, %s, %s, %s,
                           extensions.st_setsrid(extensions.st_makepoint(%s, %s), 4326)
                             ::extensions.geography)
                   on conflict (slug) do update set
                     name = excluded.name, brand = excluded.brand, kind = excluded.kind,
                     city = excluded.city, locality = excluded.locality,
                     address = excluded.address, phone = excluded.phone, geom = excluded.geom
                   returning id""",
                (p.slug, p.name, p.brand, p.kind, p.city, p.locality, p.address, p.phone,
                 p.lng, p.lat),
            )
            provider_ids[p.slug] = cur.fetchone()[0]
        counts["provider"] = len(providers)

        for s in sources:
            cur.execute(
                """insert into public.source
                     (id, provider_id, publisher, unit, city, url, doc_type, sha256,
                      as_of, retrieved, licence_note, comparison_tier)
                   values (%(id)s, %(provider_id)s, %(publisher)s, %(unit)s, %(city)s,
                           %(url)s, %(doc_type)s, %(sha256)s, %(as_of)s, %(retrieved)s,
                           %(licence_note)s, %(comparison_tier)s)
                   on conflict (id) do update set
                     provider_id = excluded.provider_id, publisher = excluded.publisher,
                     unit = excluded.unit, city = excluded.city, url = excluded.url,
                     doc_type = excluded.doc_type, sha256 = excluded.sha256,
                     as_of = excluded.as_of, retrieved = excluded.retrieved,
                     licence_note = excluded.licence_note,
                     comparison_tier = excluded.comparison_tier""",
                {**s, "provider_id": provider_ids[s["provider_slug"]]},
            )
        counts["source"] = len(sources)

        loaded = sorted({s["id"] for s in sources})
        cur.execute("delete from public.price_observation where source_id = any(%s)", (loaded,))
        with cur.copy(
            """copy public.price_observation
                 (source_id, canonical_test_id, raw_test_name, service_code, price_inr,
                  price_tier, match_confidence, match_method, needs_review)
               from stdin"""
        ) as copy:
            for r in prices.records:
                copy.write_row((r.source_id, r.canonical_test_id, r.raw_test_name,
                                r.service_code, r.price_inr, r.price_tier,
                                r.match_confidence, r.match_method, r.needs_review))
        counts["price_observation"] = len(prices.records)
    return counts
