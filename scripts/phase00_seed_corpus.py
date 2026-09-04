#!/usr/bin/env python3
"""Phase 00 - seed corpus. Deliberately throwaway.

Dumps raw test names from the confirmed sources into one CSV so the Phase 01
taxonomy has something to be measured against and the Phase 02 matcher has
messy names to work on. Phase 04 replaces this entirely with the real registry
and format adapters; nothing here is meant to survive.

What it does NOT do, on purpose:
  - crawl per-test pages. Both lab chains encode the test name in the URL slug,
    so their sitemaps alone carry every name. That is ~20 requests instead of
    ~7,000, and it keeps us inside what robots.txt plainly allows.
  - trust the PDF's own "Investigations" service type as a diagnostics filter.
    It also carries ACRYLIC CRANIOPLASTY and TEMPORARY PACEMAKER IMPLANTATION.
    Deciding what counts as a routine test is taxonomy work, not a column
    filter, so every row is emitted and Phase 01 decides.

Usage:
    python scripts/phase00_seed_corpus.py [--out data/corpus/phase00.csv]

Expects the raw documents already fetched into data/raw/ and the PDF text
already extracted into data/interim/ (see fetch_raw() below).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"

# --- source registry -------------------------------------------------------
# A flat dict here, a proper YAML registry in Stage 1. The shape is the same:
# publisher, what it is, where it came from, and what tier its prices mean.

BLOB = ("https://stgaccinwbsdevlrs01.blob.core.windows.net"
        "/newcorporatewbsite/sharing-medias/April2024")

NARAYANA_BENGALURU = {
    "source": "narayana_mazumdar_shaw_bengaluru",
    "publisher": "Narayana Health",
    "unit": "Mazumdar Shaw Medical Center, Narayana Health City, Bengaluru",
    "url": f"{BLOB}/WLrg66wGMrZnL7pNaoJd.pdf",
    "pdf": RAW / "nh-mazumdar-shaw-bengaluru-2024-01.pdf",
    "sha256": "bccb6b94316ff882ad45e55cd30d064972970eda14411c58e801860ddc9ae3e0",
    "as_of": "2024-01-01",
    "text": INTERIM / "nh-bengaluru.txt",
    # OPD | General (C) | Semi Private | SEMI DELUXE | Private | PLATINUM-B |
    # PLATINUM-A | PLATINUM SUITE | CCA | HDU | SDU
    "tiers": 11,
    "display_ok": True,
}

NARAYANA_GUWAHATI = {
    "source": "narayana_guwahati",
    "publisher": "Narayana Health",
    "unit": "Narayana Superspeciality Hospital, Guwahati",
    "url": f"{BLOB}/mNHw7DOWjOHaNP8WgQ8m.pdf",
    "pdf": RAW / "nh-guwahati-2024-01.pdf",
    "sha256": "703df84780df00abd7161e5608a14809851db5b8cb2e15f666aa77f824cd61f8",
    "as_of": "2024-01-01",
    "text": INTERIM / "nh-guwahati.txt",
    # OPD | General C | General | Semi Private | Private | Deluxe | CCA | NICU
    "tiers": 8,
    # Not a Bengaluru price. Kept for name harvesting only - the census made
    # exactly this mistake and reported Guwahati numbers as Bengaluru ones.
    "display_ok": False,
}

# Lab chains: names only. No price is harvested, so none can leak into a public
# comparison by accident.
SITEMAP_URLS = {
    "lpl-sitemap-pathology-test.xml":
        "https://www.lalpathlabs.com/sitemap-pathology-test.xml",
    "lpl-sitemap-radiology-test.xml":
        "https://www.lalpathlabs.com/sitemap-radiology-test.xml",
    **{f"rc-{i}.xml": f"https://redcliffelabs.com/sitemap{i}.xml" for i in range(1, 10)},
}

SITEMAPS = [
    ("lalpathlabs", "lpl-sitemap-pathology-test.xml", r"/pathology-test/([^/<]+)"),
    ("lalpathlabs", "lpl-sitemap-radiology-test.xml", r"/radiology-tests/([^/<]+)"),
    # national test pages: <loc>https://redcliffelabs.com/{slug}</loc>
    ("redcliffe", "rc-1.xml", r"redcliffelabs\.com/([^/<]+)</loc>"),
    ("redcliffe", "rc-*.xml", r"redcliffelabs\.com/[a-z-]+/tests/([^/<]+)"),
]

# --- fetching -------------------------------------------------------------
# robots.txt was checked for all three publishers on 2026-09-04. Narayana and
# Lal PathLabs both Allow: / ; Redcliffe disallows only campaign and landing
# paths. None of them disallow what is fetched here, and only sitemaps and
# already-public PDFs are requested - no per-test page is crawled.

UA = "ratecard-research/0.1 (student project; contact via repo)"


def fetch_raw(force: bool = False) -> None:
    """Download every source document into the immutable raw store.

    Nothing is ever overwritten in place: a changed sha256 means a new document
    and should become a new dated file, not a silent mutation of this one.
    """
    import httpx

    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "sitemaps").mkdir(exist_ok=True)

    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=120) as client:
        for spec in (NARAYANA_BENGALURU, NARAYANA_GUWAHATI):
            target = spec["pdf"]
            if target.exists() and not force:
                print(f"  cached  {target.name}")
            else:
                print(f"  GET     {spec['url']}")
                target.write_bytes(client.get(spec["url"]).content)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            status = "ok" if digest == spec["sha256"] else "CHANGED SINCE LAST FETCH"
            print(f"          sha256 {digest[:16]}... {status}")

        for name, url in SITEMAP_URLS.items():
            target = RAW / "sitemaps" / name
            if target.exists() and not force:
                continue
            print(f"  GET     {url}")
            target.write_bytes(client.get(url).content)
            time.sleep(1)  # be a polite guest


def extract_pdf_text(spec: dict) -> None:
    """PDFs have a digital text layer; no OCR involved. ~100s for 120 pages."""
    from pypdf import PdfReader

    out = spec["text"]
    if out.exists():
        print(f"  cached  {out.name}")
        return
    reader = PdfReader(spec["pdf"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(f"\n<<<PAGE {i + 1}>>>\n" + (p.extract_text() or "")
                for i, p in enumerate(reader.pages)),
        encoding="utf-8",
    )
    print(f"  parsed  {out.name} ({len(reader.pages)}pp)")


# --- PDF row parsing -------------------------------------------------------

MONEY = r"(?:[\d,]+|-)"

# Bengaluru: SVC011232 COMPLETE BLOOD COUNT (CBC) 600 810 870 ... (11 columns)
RE_BENGALURU = re.compile(
    rf"^(SVC\d+)\s+(.+?)\s+({MONEY}(?:\s+{MONEY}){{10}})\s*$", re.MULTILINE
)

# Guwahati: Investigations SVC000345 ECG 370 410 ... (8 columns)
RE_GUWAHATI = re.compile(
    rf"^([A-Za-z][A-Za-z /&-]*?)\s+(SVC\d+)\s+(.+?)\s+({MONEY}(?:\s+{MONEY}){{7}})\s*$", re.MULTILINE
)


def _price(cell: str) -> str:
    """First column is the OPD walk-in rate. '-' means not offered at that tier."""
    cell = cell.strip().replace(",", "")
    return "" if cell in {"-", ""} else cell


def parse_narayana(spec: dict) -> list[dict]:
    path = spec["text"]
    if not path.exists():
        print(f"  ! {path} missing - run the extraction step first", file=sys.stderr)
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = RE_BENGALURU if spec["tiers"] == 11 else RE_GUWAHATI
    rows = []

    for match in pattern.finditer(text):
        if spec["tiers"] == 11:
            code, name, prices = match.group(1), match.group(2), match.group(3)
            service_type = ""
        else:
            service_type, code, name, prices = match.groups()

        name = re.sub(r"\s+", " ", name).strip()
        if not name or name.lower().startswith("service name"):
            continue

        rows.append({
            "raw_name": name,
            "source": spec["source"],
            "price": _price(prices.split()[0]),
            "tier": "OPD",
            "service_code": code,
            "service_type": service_type.strip(),
            "as_of": spec["as_of"],
            "display_ok": str(spec["display_ok"]),
        })
    return rows


# --- sitemap slug harvesting ----------------------------------------------

def slug_to_name(slug: str) -> str:
    """The URL slug is the test name with hyphens for spaces. That is the whole
    trick: no page fetch needed."""
    return re.sub(r"\s+", " ", slug.replace("-", " ")).strip()


def parse_sitemaps() -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for source, glob, pattern in SITEMAPS:
        regex = re.compile(pattern, re.MULTILINE)
        for path in sorted((RAW / "sitemaps").glob(glob)):
            text = path.read_text(encoding="utf-8", errors="replace")
            for slug in regex.findall(text):
                name = slug_to_name(slug)
                if not name or len(name) < 2:
                    continue
                key = (source, name.lower())
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "raw_name": name,
                    "source": source,
                    "price": "",          # names only - see module docstring
                    "tier": "",
                    "service_code": "",
                    "service_type": "",
                    "as_of": "",
                    "display_ok": "False",
                })
    return rows


FIELDS = ["raw_name", "source", "price", "tier", "service_code",
          "service_type", "as_of", "display_ok"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/corpus/phase00.csv")
    parser.add_argument("--fetch", action="store_true", help="download sources first")
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    args = parser.parse_args()

    if args.fetch or args.force:
        fetch_raw(force=args.force)
        for spec in (NARAYANA_BENGALURU, NARAYANA_GUWAHATI):
            extract_pdf_text(spec)
        print()

    rows: list[dict] = []
    for spec in (NARAYANA_BENGALURU, NARAYANA_GUWAHATI):
        parsed = parse_narayana(spec)
        print(f"  {spec['source']:38} {len(parsed):>6} rows")
        rows.extend(parsed)

    sitemap_rows = parse_sitemaps()
    for source in sorted({r["source"] for r in sitemap_rows}):
        print(f"  {source:38} {sum(1 for r in sitemap_rows if r['source'] == source):>6} names")
    rows.extend(sitemap_rows)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    distinct = len({r["raw_name"].lower() for r in rows})
    priced = sum(1 for r in rows if r["price"])
    print(f"\n  wrote {out}")
    print(f"  {len(rows)} rows, {distinct} distinct names, {priced} carrying a price")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
