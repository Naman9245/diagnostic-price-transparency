"""Command line entry point.

    ratecard validate            validate the taxonomy, exit non-zero if broken
    ratecard stats               taxonomy shape: categories, panels, LOINC gaps
    ratecard lookup NAME...      resolve raw names through the alias index
    ratecard check A B           why two canonical tests may not be matched
    ratecard hard-negatives      seed pairs for the Phase 03 evaluation set
    ratecard coverage CORPUS.csv measure the taxonomy against a Phase 00 dump
    ratecard match CORPUS.csv    run the Stage 4 matcher over a corpus
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ratecard.names import normalise
from ratecard.normalise import explain
from ratecard.normalise.matcher import Matcher
from ratecard.taxonomy import ValidationError, load
from ratecard.taxonomy.coverage import analyse, hard_negative_pairs
from ratecard.taxonomy.loader import collect_warnings
from ratecard.taxonomy.schema import Kind

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_BELOW_TARGET = 2

COVERAGE_TARGET = 80.0


def _load_or_die():
    try:
        return load()
    except ValidationError as exc:
        print("Taxonomy is invalid.\n", file=sys.stderr)
        for problem in exc.problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID) from exc


def cmd_validate(_: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    warnings = collect_warnings(taxonomy)
    print(f"✓ taxonomy valid — {len(taxonomy)} canonical tests, "
          f"{len(taxonomy.alias_index)} indexed surface forms")
    if warnings:
        print(f"\n{len(warnings)} advisory warning(s):")
        for warning in warnings[:25]:
            print(f"  · {warning.test_id}: {warning.message}")
        if len(warnings) > 25:
            print(f"  … and {len(warnings) - 25} more")
    return EXIT_OK


def cmd_stats(_: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    by_category = taxonomy.by_category()

    print(f"{len(taxonomy)} canonical tests\n")
    width = max(len(str(c)) for c in by_category)
    for category, tests in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        panels = sum(1 for t in tests if t.is_panel)
        print(f"  {category!s:<{width}}  {len(tests):>3}   ({panels} panel)" if panels
              else f"  {category!s:<{width}}  {len(tests):>3}")

    lab = [t for t in taxonomy if t.kind is Kind.LAB]
    imaging = [t for t in taxonomy if t.kind is Kind.IMAGING]
    panels = [t for t in taxonomy if t.is_panel]
    aliases = sum(len(t.aliases) for t in taxonomy)
    with_loinc = sum(1 for t in lab if t.loinc)
    declared = sum(len(t.distinct_from) for t in taxonomy)

    print(f"\n  lab / imaging       {len(lab)} / {len(imaging)}")
    print(f"  panels              {len(panels)}")
    print(f"  aliases             {aliases} ({aliases / len(taxonomy):.1f} per test)")
    print(f"  indexed forms       {len(taxonomy.alias_index)}")
    print(f"  LOINC on lab tests  {with_loinc}/{len(lab)} ({100 * with_loinc / len(lab):.0f}%)")
    print(f"  distinct_from pairs {declared}")
    return EXIT_OK


def cmd_lookup(args: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    for raw in args.names:
        test = taxonomy.lookup(raw)
        arrow = f"{test.id:<28} [{test.category}]" if test else "— no exact match, would go to the matcher"
        print(f"  {raw!r}\n    normalised: {normalise(raw)!r}\n    resolves to: {arrow}\n")
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    missing = [i for i in (args.a, args.b) if i not in taxonomy]
    if missing:
        print(f"unknown canonical id(s): {', '.join(missing)}", file=sys.stderr)
        return EXIT_INVALID

    conflicts = explain(taxonomy[args.a], taxonomy[args.b])
    if not conflicts:
        print(f"No rule blocks {args.a} ↔ {args.b}.")
        print("The matcher's similarity passes decide this pair on their own.")
        return EXIT_OK
    print(f"BLOCKED: {args.a} ↔ {args.b}")
    for conflict in conflicts:
        print(f"  · {conflict.rule}: {conflict.detail}")
    return EXIT_OK


def cmd_hard_negatives(_: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    pairs = hard_negative_pairs(taxonomy)
    print(f"{len(pairs)} curated hard-negative pairs "
          f"(seed for the Phase 03 evaluation set)\n")
    for left, right, reason in pairs:
        print(f"  {left:<26} {right:<26} {reason}")
    return EXIT_OK


def cmd_coverage(args: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    corpus = Path(args.corpus)
    if not corpus.exists():
        print(f"Corpus not found: {corpus}", file=sys.stderr)
        print("\nPhase 00 output is not on disk. Re-run the seed dump to produce\n"
              "a CSV with a raw_name column before measuring coverage.", file=sys.stderr)
        return EXIT_INVALID

    report = analyse(taxonomy, corpus, top_unmatched=args.top)

    print(f"corpus              {corpus}")
    print(f"rows                {report.rows}")
    print(f"distinct raw names  {report.distinct_names}\n")
    print(f"  exact      {report.exact_rows:>7} rows  {report.exact_pct:5.1f}%   "
          f"({report.exact_names} distinct names) — correct by construction")
    print(f"  reachable  {report.reachable_rows:>7} rows  {report.reachable_pct:5.1f}%   "
          f"({report.reachable_names} distinct names) — containment heuristic, over-counts")

    if report.per_source:
        print("\n  by source (distinct names, exact only):")
        for source, (hits, total) in sorted(report.per_source.items()):
            print(f"    {source:<28} {hits:>6}/{total:<6} {100 * hits / total:5.1f}%")

    if report.unmatched:
        print(f"\n  curation worklist — top {len(report.unmatched)} unmatched by frequency:")
        for raw, count in report.unmatched:
            print(f"    {count:>5}  {raw}")

    passed = report.exact_pct >= COVERAGE_TARGET
    print(f"\n  exit criterion (>= {COVERAGE_TARGET:.0f}% of rows): "
          f"{'PASS' if passed else 'NOT MET'} on exact coverage")
    return EXIT_OK if passed else EXIT_BELOW_TARGET


def cmd_match(args: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    corpus = Path(args.corpus)
    if not corpus.exists():
        print(f"Corpus not found: {corpus}", file=sys.stderr)
        return EXIT_INVALID

    import collections
    import csv

    reranker = None
    if args.rerank:
        from ratecard.normalise.rerank import load_reranker
        reranker = load_reranker()
        if reranker is None:
            print("  ! sentence-transformers not installed; running lexical only\n",
                  file=sys.stderr)
    matcher = Matcher(taxonomy, reranker=reranker)
    with corpus.open(newline="", encoding="utf-8") as handle:
        names = [r["raw_name"].strip() for r in csv.DictReader(handle) if r.get("raw_name")]

    distinct = sorted(set(names))
    print(f"matching {len(distinct)} distinct names from {len(names)} rows ...\n")
    results = {name: matcher.match(name) for name in distinct}

    methods: collections.Counter[str] = collections.Counter()
    row_methods: collections.Counter[str] = collections.Counter()
    for name in names:
        row_methods[results[name].method] += 1
    for match in results.values():
        methods[match.method] += 1

    resolved_rows = sum(c for m, c in row_methods.items() if not m.startswith("abstain"))
    resolved_names = sum(c for m, c in methods.items() if not m.startswith("abstain"))

    print(f"  ROWS    {resolved_rows:>7}/{len(names):<7} resolved   "
          f"{100 * resolved_rows / len(names):5.1f}%")
    print(f"  NAMES   {resolved_names:>7}/{len(distinct):<7} resolved   "
          f"{100 * resolved_names / len(distinct):5.1f}%\n")
    for method, count in methods.most_common():
        print(f"    {method:22} {count:>7} names  {100 * count / len(distinct):5.1f}%")

    covered = {m.test_id for m in results.values() if m.test_id}
    print(f"\n  canonical tests hit: {len(covered)}/{len(taxonomy)} "
          f"({100 * len(covered) / len(taxonomy):.0f}%)")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["raw_name", "canonical_test_id", "match_confidence",
                             "match_method", "needs_review", "reason"])
            for name in distinct:
                m = results[name]
                writer.writerow([name, m.test_id or "", f"{m.confidence:.1f}",
                                 m.method, str(m.needs_review), m.reason or ""])
        print(f"\n  wrote {out}")

    if args.show:
        print(f"\n  sample of {args.show} abstentions:")
        shown = 0
        for name in distinct:
            m = results[name]
            if m.abstained and m.candidates:
                print(f"    {name[:52]:54} {m.method}")
                print(f"      └─ {(m.reason or '')[:96]}")
                shown += 1
                if shown >= args.show:
                    break
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ratecard", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate the taxonomy").set_defaults(fn=cmd_validate)
    sub.add_parser("stats", help="taxonomy shape").set_defaults(fn=cmd_stats)
    sub.add_parser("hard-negatives", help="seed pairs for evaluation").set_defaults(
        fn=cmd_hard_negatives)

    lookup = sub.add_parser("lookup", help="resolve raw names")
    lookup.add_argument("names", nargs="+")
    lookup.set_defaults(fn=cmd_lookup)

    check = sub.add_parser("check", help="why two tests may not be matched")
    check.add_argument("a")
    check.add_argument("b")
    check.set_defaults(fn=cmd_check)

    coverage = sub.add_parser("coverage", help="measure against a Phase 00 corpus")
    coverage.add_argument("corpus")
    coverage.add_argument("--top", type=int, default=40)
    coverage.set_defaults(fn=cmd_coverage)

    match_cmd = sub.add_parser("match", help="run the Stage 4 matcher over a corpus")
    match_cmd.add_argument("corpus")
    match_cmd.add_argument("--out", help="write per-name results to this CSV")
    match_cmd.add_argument("--show", type=int, default=0, help="sample N abstentions")
    match_cmd.add_argument("--rerank", action="store_true",
                           help="enable the embedding rerank (needs the rerank extra)")
    match_cmd.set_defaults(fn=cmd_match)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
