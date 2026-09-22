"""Stages 2 and 3: the raw store, the adapters, and the wiring between them."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from ratecard.fetch import RawStore, SourceChanged
from ratecard.parse import get as get_parser
from ratecard.parse import narayana_pdf, sitemap_slug
from ratecard.pipeline import child_sitemaps
from ratecard.registry import Format, Source

BENGALURU = Source(
    id="demo_hospital", publisher="Demo", url="https://example.com/x.pdf",
    format=Format.PDF, parser="narayana_pdf", city="Bengaluru",
    sha256="0" * 64, as_of=date(2024, 1, 1), display_ok=True,
    tiers=("OPD", "General", "Private"), comparison_tier="OPD",
    licence_note="test",
)
SITEMAP = Source(
    id="demo_lab", publisher="Demo Lab", url="https://example.com/s.xml",
    format=Format.SITEMAP, parser="sitemap_slug", licence_note="test",
)


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


class FakeClient:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls = 0

    def get(self, _url: str) -> FakeResponse:
        self.calls += 1
        return FakeResponse(self.content)


# --- Stage 2: the raw store ----------------------------------------------

def test_a_matching_hash_is_written_to_the_canonical_path(tmp_path):
    import hashlib

    data = b"pretend pdf"
    source = replace(BENGALURU, sha256=hashlib.sha256(data).hexdigest())
    store = RawStore(tmp_path)
    result = store.fetch(source, FakeClient(data))
    assert result.path == tmp_path / "demo_hospital.pdf"
    assert result.path.read_bytes() == data
    assert not result.from_cache


def test_a_changed_document_never_overwrites_and_stops_the_run(tmp_path):
    """The parsers are written against exact documents. A reissue is an event."""
    store = RawStore(tmp_path)
    store.path_for(BENGALURU).write_bytes(b"the known document")

    with pytest.raises(SourceChanged, match="has changed at the publisher"):
        store.fetch(BENGALURU, FakeClient(b"something else"), force=True)

    assert store.path_for(BENGALURU).read_bytes() == b"the known document"
    sidecars = list(tmp_path.glob("demo_hospital.fetched-*.pdf"))
    assert len(sidecars) == 1
    assert sidecars[0].read_bytes() == b"something else"


def test_a_tampered_cached_file_is_caught_without_a_network_call(tmp_path):
    store = RawStore(tmp_path)
    store.path_for(BENGALURU).write_bytes(b"tampered")
    client = FakeClient(b"irrelevant")
    with pytest.raises(SourceChanged, match="does not match the registry pin"):
        store.fetch(BENGALURU, client)
    assert client.calls == 0


def test_an_unpinned_source_is_allowed_to_drift(tmp_path):
    """Sitemaps grow as catalogues do; there is nothing to betray."""
    store = RawStore(tmp_path)
    store.fetch(SITEMAP, FakeClient(b"<urlset/>"))
    store.fetch(SITEMAP, FakeClient(b"<urlset>more</urlset>"), force=True)
    assert store.path_for(SITEMAP).read_bytes() == b"<urlset>more</urlset>"


def test_cache_hit_skips_the_network(tmp_path):
    import hashlib

    data = b"cached"
    source = replace(BENGALURU, sha256=hashlib.sha256(data).hexdigest())
    store = RawStore(tmp_path)
    store.path_for(source).write_bytes(data)
    client = FakeClient(data)
    assert store.fetch(source, client).from_cache
    assert client.calls == 0


# --- Stage 3: the PDF adapter --------------------------------------------

THREE_TIER = """
Service Type Athma Code Service Name OPD General Private
Investigations SVC000001 COMPLETE BLOOD COUNT (CBC) 600 810 870
Investigations SVC000002 LIPID PROFILE 1,520 2,060 2,210
SVC000003 TSH 860 950 950 Investigations
Investigations SVC000004
SPUTUM FOR AFB 250 275 275
Investigations SVC000005 BROKEN ROW WITH NO PRICES
"""


def test_tier_count_comes_from_the_registry_not_the_code():
    result = narayana_pdf.parse(THREE_TIER, BENGALURU)
    names = {r.raw_name for r in result.rows}
    assert "COMPLETE BLOOD COUNT (CBC)" in names


def test_the_comparison_tier_is_the_column_that_is_read():
    result = narayana_pdf.parse(THREE_TIER, BENGALURU)
    by_name = {r.raw_name: r for r in result.rows}
    assert by_name["COMPLETE BLOOD COUNT (CBC)"].price == "600"
    assert by_name["LIPID PROFILE"].price == "1520", "commas must be stripped"


def test_a_trailing_service_type_still_parses():
    """Some pages put the service type after the prices instead of before."""
    assert "TSH" in {r.raw_name for r in narayana_pdf.parse(THREE_TIER, BENGALURU).rows}


def test_wrapped_rows_are_rejoined():
    """Long names push the price run onto the next line. Requiring one line
    silently dropped 291 of Guwahati's 1,792 rows."""
    assert "SPUTUM FOR AFB" in {r.raw_name for r in narayana_pdf.parse(THREE_TIER, BENGALURU).rows}


def test_rows_that_cannot_be_parsed_are_counted_not_dropped():
    assert narayana_pdf.parse(THREE_TIER, BENGALURU).unparsed >= 1


def test_provenance_travels_on_every_row():
    for row in narayana_pdf.parse(THREE_TIER, BENGALURU).rows:
        assert row.source_id == "demo_hospital"
        assert row.as_of == date(2024, 1, 1)
        assert row.tier == "OPD"
        assert row.display_ok is True


def test_display_ok_false_travels_too():
    guwahati = replace(BENGALURU, id="demo_other", display_ok=False, city="Guwahati")
    assert all(not r.display_ok for r in narayana_pdf.parse(THREE_TIER, guwahati).rows)


def test_a_source_with_no_tiers_cannot_be_pdf_parsed():
    bare = replace(BENGALURU, tiers=(), comparison_tier=None)
    with pytest.raises(ValueError, match="at least two price tiers"):
        narayana_pdf.parse(THREE_TIER, bare)


# --- Stage 3: the sitemap adapter ----------------------------------------

SITEMAP_XML = """<urlset>
<loc>https://lab.com/pathology-test/hba1c</loc>
<loc>https://lab.com/pathology-test/cholesterol-total?q=chol</loc>
<loc>https://lab.com/pathology-test/urine%20routine</loc>
<loc>https://lab.com/bangalore/tests/lipid-profile</loc>
<loc>https://lab.com/bangalore</loc>
<loc>https://lab.com/book-radiology-test</loc>
<loc>https://lab.com/faq</loc>
<loc>https://lab.com/a/b/c/d/deep</loc>
</urlset>"""


def test_query_strings_do_not_end_up_in_the_name():
    names = {r.raw_name for r in sitemap_slug.parse([SITEMAP_XML], SITEMAP).rows}
    assert "cholesterol total" in names
    assert not any("?" in n for n in names)


def test_percent_encoding_is_decoded():
    names = {r.raw_name for r in sitemap_slug.parse([SITEMAP_XML], SITEMAP).rows}
    assert "urine routine" in names
    assert not any("%" in n for n in names)


def test_city_landing_pages_are_excluded_by_asking_the_site():
    """A slug that also appears as a /{city}/tests/ segment is a city."""
    names = {r.raw_name for r in sitemap_slug.parse([SITEMAP_XML], SITEMAP).rows}
    assert "bangalore" not in names
    assert "lipid profile" in names


def test_navigation_pages_are_excluded():
    names = {r.raw_name for r in sitemap_slug.parse([SITEMAP_XML], SITEMAP).rows}
    assert "book radiology test" not in names
    assert "faq" not in names


def test_sitemap_rows_never_carry_a_price():
    for row in sitemap_slug.parse([SITEMAP_XML], SITEMAP).rows:
        assert row.price is None
        assert row.display_ok is False


def test_deliberate_skips_are_not_reported_as_failures():
    result = sitemap_slug.parse([SITEMAP_XML], SITEMAP)
    assert result.unparsed == 0
    assert result.skipped > 0


# --- wiring ----------------------------------------------------------------

def test_child_sitemaps_detected_regardless_of_wrapper_element():
    """Redcliffe publishes its index as a <urlset>, not a <sitemapindex>."""
    as_urlset = "<urlset><loc>https://x/sitemap1.xml</loc><loc>https://x/page</loc></urlset>"
    assert child_sitemaps(as_urlset) == ["https://x/sitemap1.xml"]
    assert child_sitemaps("<urlset><loc>https://x/page</loc></urlset>") == []


def test_parser_lookup_names_what_is_available():
    assert get_parser("narayana_pdf") is narayana_pdf
    with pytest.raises(KeyError, match="no parser named"):
        get_parser("does_not_exist")


def test_every_registry_parser_actually_exists():
    """A registry entry naming a parser that is not registered would fail at
    ingest time rather than load time; catch it here instead."""
    from ratecard.registry import load

    for source in load():
        assert get_parser(source.parser) is not None


def test_store_paths_are_derived_from_the_source_id():
    store = RawStore(Path("/tmp/x"))
    assert store.path_for(BENGALURU).name == "demo_hospital.pdf"
    assert store.path_for(SITEMAP).name == "demo_lab.xml"
