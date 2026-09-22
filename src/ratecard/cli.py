"""Command line entry point.

    ratecard validate            validate the taxonomy, exit non-zero if broken
    ratecard stats               taxonomy shape: categories, panels, LOINC gaps
    ratecard lookup NAME...      resolve raw names through the alias index
    ratecard check A B           why two canonical tests may not be matched
    ratecard hard-negatives      seed pairs for the Phase 03 evaluation set
    ratecard coverage CORPUS.csv measure the taxonomy against a Phase 00 dump
    ratecard sources             the Stage 1 source registry
    ratecard ingest              stages 1-3: registry -> fetch -> parse -> CSV
    ratecard match CORPUS.csv    run the Stage 4 matcher over a corpus

Phase 03, in this order and no other:
    ratecard sample CORPUS.csv   draw the stratified labelling set
    ratecard label LABELS.csv    label it by hand, before tuning anything
    ratecard evaluate LABELS.csv score the matcher against those labels
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ratecard.evaluate.labelling import LabelSession
from ratecard.evaluate.labelling import run as run_labelling
from ratecard.evaluate.metrics import evaluate as run_evaluate
from ratecard.evaluate.sampling import STRATA, build_sample, write_sample
from ratecard.names import normalise
from ratecard.normalise import explain
from ratecard.registry import RegistryError
from ratecard.registry import load as load_registry
from ratecard.taxonomy import ValidationError, load
from ratecard.taxonomy.coverage import analyse, hard_negative_pairs
from ratecard.taxonomy.loader import collect_warnings
from ratecard.taxonomy.schema import Kind

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_BELOW_TARGET = 2

COVERAGE_TARGET = 80.0


def _require_matcher():
    """Import the Matcher class, or exit with something a human can act on.

    `validate`, `stats`, `lookup`, `check` and `hard-negatives` are pure
    taxonomy operations and must keep working on a machine with nothing but
    stdlib and PyYAML - that promise is in the README, and importing the
    matcher at module scope quietly broke it for every subcommand.
    """
    try:
        from ratecard.normalise.matcher import Matcher
    except ImportError as exc:
        print(f"This command needs the matcher, which needs rapidfuzz: {exc}\n"
              f"  pip install -e '.[normalise]'", file=sys.stderr)
        raise SystemExit(EXIT_INVALID) from exc
    return Matcher


def _matcher_or_die(taxonomy, reranker=None):
    return _require_matcher()(taxonomy, reranker=reranker)


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


def cmd_sources(_: argparse.Namespace) -> int:
    try:
        registry = load_registry()
    except RegistryError as exc:
        print("Source registry is invalid.\n", file=sys.stderr)
        for problem in exc.problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        return EXIT_INVALID

    print(f"{len(registry)} sources\n")
    for source in registry:
        flag = "displayable" if source.display_ok else "names only"
        where = f"{source.city}" if source.city else "—"
        print(f"  {source.id}")
        print(f"    {source.publisher}  ·  {where}  ·  {source.format}  ·  {flag}")
        if source.carries_prices:
            print(f"    {len(source.tiers)} tiers, comparing on "
                  f"{source.comparison_tier!r} (column {source.comparison_index + 1})")
        if source.as_of:
            print(f"    as of {source.as_of}, retrieved {source.retrieved}")
        print()

    displayable = registry.displayable()
    print(f"  {len(displayable)} source(s) may have prices shown publicly: "
          f"{', '.join(s.id for s in displayable) or 'none'}")
    if len(displayable) < 2:
        print("\n  ! A price comparison needs more than one provider. Extending")
        print("  ! this registry is the substance of Phase 04, not the plumbing.")
    return EXIT_OK


def cmd_ingest(args: argparse.Namespace) -> int:
    """Stages 1-3. Replaces scripts/phase00_seed_corpus.py."""
    import csv as csv_module

    from ratecard.fetch import RawStore, SourceChanged, fetch_all
    from ratecard.parse.rows import FIELDS as ROW_FIELDS
    from ratecard.pipeline import ingest_all

    try:
        registry = load_registry()
    except RegistryError as exc:
        print("Source registry is invalid.\n", file=sys.stderr)
        for problem in exc.problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        return EXIT_INVALID

    store = RawStore(Path(args.raw))
    interim = Path(args.interim)

    if args.fetch:
        try:
            for result in fetch_all(registry, store, force=args.force):
                state = "cached" if result.from_cache else "GET   "
                print(f"  {state}  {result.source_id:36} {result.sha256[:16]}...")
        except SourceChanged as exc:
            print(f"\nSTOPPED: {exc}", file=sys.stderr)
            return EXIT_INVALID
        print()

    rows = []
    for result in ingest_all(registry, store, interim):
        bits = []
        if result.unparsed:
            bits.append(f"{result.unparsed} unparsed")
        if result.skipped:
            bits.append(f"{result.skipped:,} skipped")
        if result.documents > 1:
            bits.append(f"{result.documents} docs")
        note = f"   {', '.join(bits)}" if bits else ""
        print(f"  {result.source_id:36} {len(result.rows):>6} rows{note}")
        rows.extend(result.rows)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv_module.DictWriter(handle, fieldnames=ROW_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())

    distinct = len({r.raw_name.lower() for r in rows})
    priced = sum(1 for r in rows if r.price)
    shown = sum(1 for r in rows if r.display_ok and r.price)
    print(f"\n  wrote {out}")
    print(f"  {len(rows)} rows, {distinct} distinct names, {priced} priced, "
          f"{shown} of those displayable")
    return EXIT_OK


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
    matcher = _matcher_or_die(taxonomy, reranker)
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


def cmd_sample(args: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    corpus = Path(args.corpus)
    if not corpus.exists():
        print(f"Corpus not found: {corpus}", file=sys.stderr)
        return EXIT_INVALID

    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"{out} already exists. Re-drawing would discard existing labels.\n"
              f"Pass --force only if you are certain.", file=sys.stderr)
        return EXIT_INVALID

    _require_matcher()  # fail with a usable message, not a traceback
    print(f"matching {corpus} to bucket by stratum ...\n")
    rows, population = build_sample(taxonomy, corpus, seed=args.seed)
    write_sample(rows, out, population)

    total_population = sum(population.values())
    print(f"{'stratum':30} {'drawn':>6} {'of':>7}  {'share':>6}   why")
    for stratum, (_quota, why) in STRATA.items():
        drawn = sum(1 for r in rows if r.stratum == stratum)
        size = population.get(stratum, 0)
        share = 100 * size / total_population if total_population else 0
        print(f"  {stratum:28} {drawn:>6} {size:>7}  {share:5.1f}%   {why}")

    holdout = sum(1 for r in rows if r.split == "holdout")
    print(f"\n  {len(rows)} rows drawn: {len(rows) - holdout} train, {holdout} holdout")
    print(f"  wrote {out}")
    print("\n  The sample is STRATIFIED, not uniform. Rates measured on it are not")
    print("  corpus rates - `ratecard evaluate` reweights by the sizes above.")
    print(f"\n  Next: ratecard label {out}")
    return EXIT_OK


def cmd_label(args: argparse.Namespace) -> int:
    taxonomy = _load_or_die()
    labels = Path(args.labels)
    if not labels.exists():
        print(f"No labelling set at {labels}. Run `ratecard sample` first.", file=sys.stderr)
        return EXIT_INVALID
    session = LabelSession.load(labels, labelled_by=args.by)
    return run_labelling(session, taxonomy)


def cmd_evaluate(args: argparse.Namespace) -> int:
    _load_or_die()
    labels = Path(args.labels)
    if not labels.exists():
        print(f"No labelling set at {labels}.", file=sys.stderr)
        return EXIT_INVALID

    if args.split == "holdout":
        print("  ! Holdout split. This is meant to be read once, after every")
        print("  ! threshold is frozen. Re-reading it while tuning turns it")
        print("  ! into a second training set.\n", file=sys.stderr)

    metrics = run_evaluate(labels, split=None if args.split == "all" else args.split)
    scored, total = len(metrics.scored), len(metrics.judgements)
    if not scored:
        print(f"Nothing labelled yet in split '{args.split}'. "
              f"Run `ratecard label {labels}`.", file=sys.stderr)
        return EXIT_INVALID

    counts = metrics.counts()
    print(f"split={args.split}   {scored} scored of {total} "
          f"({total - scored} unsure or unlabelled)\n")
    for outcome, count in counts.most_common():
        print(f"    {outcome:22} {count:>5}  {100 * count / scored:5.1f}%")

    def pct(value):
        return "     —" if value is None else f"{100 * value:5.1f}%"

    print("\n  rate                 estimate  95% interval   what it means")
    for metric, blurb in [
        ("precision", "of the answers it gave, how many were right"),
        ("recall", "of answerable rows, how many it got"),
        ("coverage", "how often it answered at all"),
        ("abstention_precision", "when it refused, was refusing right"),
    ]:
        print(f"  {metric.replace('_', ' '):20} {metrics.estimate(metric)!s:28} {blurb}")
    print(f"  {'F1':20} {pct(metrics.f1())}")

    hard = metrics.estimate("hard_negative_precision")
    print(f"\n  HARD-NEGATIVE ACCURACY {hard!s}   <- the number worth quoting")

    # An interval this wide is not a finding. Say so rather than let a point
    # estimate off 26 rows get quoted as though it were measured.
    wide = [(m, e) for m in ("precision", "hard_negative_precision")
            if (e := metrics.estimate(m)).width and e.width > 0.20]
    if wide:
        print("\n  ! too few labels to conclude:")
        for metric, estimate in wide:
            need = estimate.labels_needed_for(0.10)
            print(f"  !   {metric.replace('_', ' '):24} interval is "
                  f"{100 * estimate.width:.0f} points wide at n={estimate.total}"
                  + (f"; ~{need} more labels would halve it" if need else ""))

    if metrics.population:
        print("\n  reweighted to corpus (the sample is stratified, so the figures")
        print("  above are not corpus rates):")
        print(f"    precision {pct(metrics.corpus_estimate('precision'))}   "
              f"recall {pct(metrics.corpus_estimate('recall'))}   "
              f"coverage {pct(metrics.corpus_estimate('coverage'))}")
    else:
        print("\n  ! no population sidecar beside the labels, so no corpus-level")
        print("  ! estimate is possible. The figures above are SAMPLE rates on a")
        print("  ! stratified draw - do not quote them as corpus rates.")

    by_stratum = metrics.by_stratum()
    if len(by_stratum) > 1:
        print("\n  by stratum:")
        for stratum in sorted(by_stratum):
            print(f"    {stratum:30} precision {pct(metrics.precision(stratum))}  "
                  f"n={sum(by_stratum[stratum].values())}")

    worst = metrics.worst(args.worst)
    if worst:
        print(f"\n  confidently wrong - the {len(worst)} to explain in the write-up:")
        for j in worst:
            print(f"    {j.confidence:5.1f}  {j.raw_name[:44]:46} "
                  f"said {j.guess or '—'}, is {j.label}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ratecard", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate the taxonomy").set_defaults(fn=cmd_validate)
    sub.add_parser("stats", help="taxonomy shape").set_defaults(fn=cmd_stats)
    sub.add_parser("hard-negatives", help="seed pairs for evaluation").set_defaults(
        fn=cmd_hard_negatives)
    sub.add_parser("sources", help="the Stage 1 source registry").set_defaults(
        fn=cmd_sources)

    ingest = sub.add_parser("ingest", help="stages 1-3: registry -> fetch -> parse")
    ingest.add_argument("--out", default="data/corpus/phase00.csv")
    ingest.add_argument("--raw", default="data/raw")
    ingest.add_argument("--interim", default="data/interim")
    ingest.add_argument("--fetch", action="store_true", help="download first")
    ingest.add_argument("--force", action="store_true", help="re-download even if cached")
    ingest.set_defaults(fn=cmd_ingest)

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

    sample = sub.add_parser("sample", help="draw the stratified labelling set")
    sample.add_argument("corpus")
    sample.add_argument("--out", default="data/eval/labels.csv")
    sample.add_argument("--seed", type=int, default=20260905)
    sample.add_argument("--force", action="store_true", help="overwrite existing labels")
    sample.set_defaults(fn=cmd_sample)

    label = sub.add_parser("label", help="label the sample by hand")
    label.add_argument("labels", nargs="?", default="data/eval/labels.csv")
    label.add_argument("--by", default="", help="who is labelling")
    label.set_defaults(fn=cmd_label)

    ev = sub.add_parser("evaluate", help="score the matcher against the labels")
    ev.add_argument("labels", nargs="?", default="data/eval/labels.csv")
    ev.add_argument("--split", choices=["train", "holdout", "all"], default="train")
    ev.add_argument("--worst", type=int, default=20)
    ev.set_defaults(fn=cmd_evaluate)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
