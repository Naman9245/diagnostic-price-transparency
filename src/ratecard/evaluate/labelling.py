"""Interactive labelling for the Phase 03 evaluation set.

Two properties matter more than speed here.

**Nothing is ever lost.** The file is rewritten after every single label, and
the session resumes from the first unlabelled row. Losing an afternoon of
labelling to a closed terminal would be the worst possible failure of this
tool, so it does the paranoid thing on every keystroke rather than the fast one.

**The matcher's answer is hidden.** The candidate pool is shown, because 210
options is more than anyone can hold in their head, but not which candidate the
matcher picked, nor its score, and the list is sorted by id rather than by
rank. A labeller shown "the machine thinks this is cbc, agree?" will agree far
more often than they should, and that inflates exactly the number this exercise
exists to measure honestly.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path

from ratecard.evaluate.metrics import NONE_LABEL, UNSURE_LABEL
from ratecard.evaluate.sampling import FIELDS
from ratecard.names import normalise
from ratecard.taxonomy.loader import Taxonomy


@dataclass
class LabelSession:
    """Rows plus the read/modify/save cycle. No terminal I/O lives here."""

    path: Path
    rows: list[dict[str, str]] = field(default_factory=list)
    labelled_by: str = ""

    @classmethod
    def load(cls, path: Path, labelled_by: str = "") -> LabelSession:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return cls(path=path, rows=rows, labelled_by=labelled_by)

    # -- progress --------------------------------------------------------
    @property
    def done(self) -> int:
        return sum(1 for r in self.rows if (r.get("label") or "").strip())

    @property
    def total(self) -> int:
        return len(self.rows)

    def pending(self) -> list[int]:
        return [i for i, r in enumerate(self.rows) if not (r.get("label") or "").strip()]

    # -- mutation --------------------------------------------------------
    def record(self, index: int, label: str, note: str = "") -> None:
        self.rows[index]["label"] = label
        self.rows[index]["labelled_by"] = self.labelled_by
        if note:
            self.rows[index]["note"] = note
        self.save()

    def save(self) -> None:
        """Full rewrite via a temporary file, so an interrupted write cannot
        truncate hours of work."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for row in self.rows:
                writer.writerow({key: row.get(key, "") for key in FIELDS})
        tmp.replace(self.path)


def search(taxonomy: Taxonomy, query: str, limit: int = 12) -> list[str]:
    """Substring search over ids, names and aliases, for when the candidate
    pool does not contain the right answer."""
    needle = normalise(query)
    if not needle:
        return []
    hits: list[str] = []
    for test in taxonomy:
        haystacks = [test.id.replace("_", " "), normalise(test.name)]
        haystacks += [normalise(a) for a in test.aliases]
        if any(needle in h for h in haystacks):
            hits.append(test.id)
        if len(hits) >= limit:
            break
    return hits


HELP = """
  1-9        label with that candidate      =<id>   label with any canonical id
  n          none of them fit               ?<text> search the taxonomy
  u          unsure - excluded from metrics .       repeat your last label
  z          undo the last label            s       skip for now
  h          this help                      q       save and quit
"""

# What each stratum is asking you to decide. Shown once when it comes up,
# because labelling 60 rows of one kind in a row is much faster than
# switching decision mode every row.
STRATUM_BRIEF = {
    "exact": "An alias matched exactly. You are checking the ALIAS, not the matcher - "
             "is that surface form really this test?",
    "lexical": "The matcher committed to an answer. This is where confident errors "
               "live, so read the name before you read the options.",
    "abstain_thin_margin": "Two candidates scored close together. Often the right "
                           "answer is 'none' - do not force a pick.",
    "declared_distinct_neighbour": "The top two are a curated confusable pair. These "
                                   "are the hard negatives; take your time.",
    "abstain_low_score": "Nothing scored well. Did the matcher miss something obvious?",
    "abstain_no_candidate": "Nothing was even considered. Mostly surgery and "
                            "specialist assays - expect 'n' for most of these.",
    "abstain_vetoed": "Every candidate was ruled out by a hard rule. Was the rule right?",
}


def _describe(test) -> str:
    """One line of context so the labeller need not recall the taxonomy."""
    bits = [str(test.category).replace("_", " ")]
    if test.specimen:
        bits.append(str(test.specimen).replace("_", " "))
    if test.modality:
        bits.append(str(test.modality))
    if test.is_panel:
        bits.append(f"panel of {test.analyte_count}")
    return " · ".join(bits)


def _bar(done: int, total: int, width: int = 22) -> str:
    filled = round(width * done / total) if total else 0
    return "▓" * filled + "░" * (width - filled)


def _eta(done_now: int, remaining: int, elapsed: float) -> str:
    if done_now < 3 or elapsed <= 0:
        return ""
    rate = elapsed / done_now
    left = int(rate * remaining)
    if left < 90:
        return f"~{left}s left"
    if left < 5400:
        return f"~{left // 60}m left"
    return f"~{left // 3600}h {(left % 3600) // 60}m left"


def run(session: LabelSession, taxonomy: Taxonomy, read=input, write=print) -> int:
    """Terminal loop. `read`/`write` are injected so this can be driven in tests."""
    pending = session.pending()
    if not pending:
        write(f"All {session.total} rows are already labelled.")
        return 0

    # Group by stratum: staying in one decision mode is far quicker than
    # switching every row, and the brief only has to be read once per group.
    pending.sort(key=lambda i: (session.rows[i]["stratum"], session.rows[i]["raw_name"]))

    write(f"\n{session.done}/{session.total} labelled. {len(pending)} to go.")
    write("The matcher's own answer is deliberately not shown. Type h for help.")

    started = time.monotonic()
    labelled_now = 0
    last_label: str | None = None
    history: list[int] = []
    current_stratum: str | None = None

    position = 0
    while position < len(pending):
        index = pending[position]
        row = session.rows[index]
        candidates = [c for c in (row.get("candidates") or "").split("|") if c]

        if row["stratum"] != current_stratum:
            current_stratum = row["stratum"]
            remaining = sum(1 for i in pending[position:]
                            if session.rows[i]["stratum"] == current_stratum)
            write(f"\n{'═' * 66}\n  {current_stratum.upper()}  ({remaining} rows)")
            write(f"  {STRATUM_BRIEF.get(current_stratum, '')}\n{'═' * 66}")

        recorded = False
        while not recorded:
            eta = _eta(labelled_now, len(pending) - position, time.monotonic() - started)
            write(f"\n─── {position + 1}/{len(pending)}  {_bar(position, len(pending))}  "
                  f"{100 * position // len(pending)}%   {eta}")
            write(f"    seen in {row['row_count']} row(s) · {row['sources']}")
            write(f"\n    {row['raw_name']}\n")
            if candidates:
                for n, test_id in enumerate(candidates, start=1):
                    test = taxonomy[test_id]
                    write(f"      {n}. {test.name[:38]:40} {_describe(test)}")
            else:
                write("      (nothing plausible was found - ?search, or n)")

            try:
                answer = read("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                write("\nSaved. Run the same command again to resume.")
                return 0

            if answer == "q":
                write(f"\nSaved. {session.done}/{session.total} labelled.")
                return 0
            if answer in {"h", "help"}:
                write(HELP)
                continue
            if answer == "z":
                if not history:
                    write("      nothing to undo")
                    continue
                previous = history.pop()
                session.record(previous, "")
                labelled_now = max(0, labelled_now - 1)
                position = pending.index(previous)
                write(f"      undone: {session.rows[previous]['raw_name'][:50]}")
                recorded = True
                continue
            if answer == "s":
                position += 1
                recorded = True
                continue
            if answer.startswith("?"):
                found = search(taxonomy, answer[1:])
                if not found:
                    write("      no match")
                for test_id in found:
                    write(f"      = {test_id:30} {taxonomy[test_id].name[:34]:36} "
                          f"{_describe(taxonomy[test_id])}")
                continue

            choice: str | None = None
            if answer == ".":
                if last_label is None:
                    write("      no previous label to repeat")
                    continue
                choice = last_label
            elif answer.startswith("="):
                test_id = answer[1:].strip()
                if test_id not in taxonomy:
                    write(f"      '{test_id}' is not a canonical id")
                    continue
                choice = test_id
            elif answer == "n":
                choice = NONE_LABEL
            elif answer == "u":
                choice = UNSURE_LABEL
            elif answer.isdigit() and 1 <= int(answer) <= len(candidates):
                choice = candidates[int(answer) - 1]
            else:
                write("      unrecognised - type h for help")
                continue

            session.record(index, choice)
            history.append(index)
            last_label = choice
            labelled_now += 1
            position += 1
            recorded = True

    write(f"\nDone. {session.done}/{session.total} labelled.")
    return 0
