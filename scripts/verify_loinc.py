#!/usr/bin/env python3
"""Check every LOINC code in the taxonomy against the real LOINC release.

The codes were seeded from model memory rather than a fetched release, which
means some of them are plausible-looking and wrong. A wrong code is worse than
an absent one: it looks authoritative, and nothing downstream can detect it.

Source is the NLM Clinical Table Search Service, a free public endpoint over
the official LOINC table - no licence key, unlike fhir.loinc.org.

Two kinds of finding, and only one of them is decidable by a machine:

    INVALID   the code does not exist in LOINC at all. Definitely wrong.
    SUSPECT   the code exists, but its official name looks nothing like the
              test we attached it to. Needs a human to look.

Usage:
    python scripts/verify_loinc.py                 # report only
    python scripts/verify_loinc.py --null-invalid  # also strip invalid codes
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ratecard.names import normalise
from ratecard.taxonomy import load
from ratecard.taxonomy.loader import DATA_DIR

API = "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search"
UA = "ratecard-research/0.1 (student project; verifying seeded LOINC codes)"

# Below this WRatio between our name and LOINC's long common name, a human
# should look. Not a correctness threshold - a triage one.
SUSPECT_BELOW = 45.0

# Codes whose official LOINC name looks nothing like ours but which are right -
# LOINC names the analyte, Indian rate cards name the assay. Checked by hand on
# 2026-09-13; listed so a clean run reports zero findings and a new finding
# means something. Remove an entry if you change that test's code.
REVIEWED_SYNONYMS = {
    "vdrl": "RPR is the modern reagin assay VDRL refers to",
    "beta_hcg": "choriogonadotropin is hCG",
    "nt_probnp": "natriuretic peptide B prohormone N-terminal is NT-proBNP",
    "vitamin_d_1_25_dihydroxy": "calcitriol is 1,25-dihydroxyvitamin D",
    "sgpt_alt": "alanine aminotransferase is SGPT",
    "sgot_ast": "aspartate aminotransferase is SGOT",
    "egfr": "glomerular filtration rate, estimated",
    "g6pd": "G6PD enzymatic activity in red blood cells",
    "anti_tpo": "thyroperoxidase IgG Ab is anti-TPO",
    "sputum_afb": "acid fast stain microscopy",
    "glucose_random": "plain serum glucose is what a random sugar measures",
    "growth_hormone": "somatotropin is growth hormone",
    "peripheral_smear": "leukocyte morphology in blood",
    "inr": "INR",
    "aptt": "aPTT",
}
PAUSE = 0.34  # be a polite guest on a free public endpoint


def lookup(code: str) -> str | None:
    """Official LONG_COMMON_NAME for a code, or None when LOINC has no such code."""
    # maxList must be generous: the endpoint does a text search, so a short
    # code like "600-7" can be pushed past a small window by partial matches.
    # With maxList=5 it reported the perfectly valid 600-7 as non-existent.
    query = urllib.parse.urlencode({
        "terms": code, "df": "LOINC_NUM,LONG_COMMON_NAME", "maxList": 200,
    })
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    for returned_code, name in payload[3] or []:
        if returned_code == code:
            return name
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--null-invalid", action="store_true",
                        help="strip codes LOINC does not recognise")
    parser.add_argument("--limit", type=int, default=0, help="check only the first N")
    args = parser.parse_args()

    taxonomy = load()
    coded = [t for t in taxonomy if t.loinc]
    if args.limit:
        coded = coded[: args.limit]

    try:
        from rapidfuzz import fuzz
        score = fuzz.WRatio
    except ImportError:
        score = None

    invalid: list[tuple[str, str]] = []
    suspect: list[tuple[str, str, str, float]] = []
    ok = 0

    print(f"checking {len(coded)} codes against the NLM LOINC table ...\n")
    for n, test in enumerate(coded, start=1):
        try:
            official = lookup(test.loinc)
        except Exception as exc:  # noqa: BLE001 - network, report and continue
            print(f"  ? {test.id:30} {test.loinc:10} lookup failed: {exc}")
            continue

        if official is None:
            invalid.append((test.id, test.loinc))
            print(f"  ✗ {test.id:30} {test.loinc:10} NOT A LOINC CODE")
        else:
            similarity = score(normalise(test.name), normalise(official)) if score else 100.0
            if similarity < SUSPECT_BELOW and test.id not in REVIEWED_SYNONYMS:
                suspect.append((test.id, test.loinc, official, similarity))
                print(f"  ? {test.id:30} {test.loinc:10} {official[:52]}")
            else:
                ok += 1
        if n % 25 == 0:
            print(f"    ... {n}/{len(coded)}")
        time.sleep(PAUSE)

    print(f"\n  {ok} look right "
          f"({len(REVIEWED_SYNONYMS)} of them via the reviewed-synonym list)")
    print(f"  {len(suspect)} suspect - the code is real but the name does not match")
    print(f"  {len(invalid)} INVALID - no such LOINC code")

    if suspect:
        print("\n  suspect, needs a human:")
        for test_id, code, official, similarity in sorted(suspect, key=lambda x: x[3]):
            print(f"    {test_id:28} {code:10} {similarity:4.0f}  LOINC says: {official[:56]}")

    if invalid and args.null_invalid:
        stripped = 0
        for path in sorted(DATA_DIR.glob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            for test_id, code in invalid:
                needle = f'  loinc: "{code}"\n'
                if f"- id: {test_id}\n" in text and needle in text:
                    text = text.replace(needle, "", 1)
                    stripped += 1
            path.write_text(text, encoding="utf-8")
        print(f"\n  stripped {stripped} invalid code(s). Re-run `ratecard validate`.")
    elif invalid:
        print("\n  re-run with --null-invalid to strip them")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
