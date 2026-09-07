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
from dataclasses import dataclass, field
from pathlib import Path

from ratecard.evaluate.metrics import NONE_LABEL, UNSURE_LABEL
from ratecard.evaluate.sampling import FIELDS
from ratecard.names import normalise
from ratecard.taxonomy.loader import Taxonomy

SKIP = object()


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
  u          unsure - excluded from metrics s       skip for now
  h          this help                      q       save and quit
"""


def run(session: LabelSession, taxonomy: Taxonomy, read=input, write=print) -> int:
    """Terminal loop. `read`/`write` are injected so this can be driven in tests."""
    pending = session.pending()
    if not pending:
        write(f"All {session.total} rows are already labelled.")
        return 0

    write(f"\n{session.done}/{session.total} labelled. {len(pending)} to go.")
    write("The matcher's own answer is deliberately not shown. Type h for help.\n")

    for position, index in enumerate(pending, start=1):
        row = session.rows[index]
        candidates = [c for c in (row.get("candidates") or "").split("|") if c]

        while True:
            write(f"\n─── {position}/{len(pending)}  [{row['stratum']}] "
                  f"seen in {row['row_count']} row(s): {row['sources']}")
            write(f"    {row['raw_name']}")
            if candidates:
                for n, test_id in enumerate(candidates, start=1):
                    write(f"      {n}. {test_id:32} {taxonomy[test_id].name}")
            else:
                write("      (no candidates - use ?search or n)")

            try:
                answer = read("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                write("\nSaved. Run the same command again to resume.")
                return 0

            if answer == "q":
                write(f"\nSaved. {session.done}/{session.total} labelled.")
                return 0
            if answer in {"h", "help", "?"}:
                write(HELP)
                continue
            if answer == "s":
                break
            if answer.startswith("?"):
                found = search(taxonomy, answer[1:])
                if not found:
                    write("      no match")
                else:
                    for test_id in found:
                        write(f"      = {test_id:32} {taxonomy[test_id].name}")
                continue
            if answer.startswith("="):
                test_id = answer[1:].strip()
                if test_id not in taxonomy:
                    write(f"      '{test_id}' is not a canonical id")
                    continue
                session.record(index, test_id)
                break
            if answer == "n":
                session.record(index, NONE_LABEL)
                break
            if answer == "u":
                session.record(index, UNSURE_LABEL)
                break
            if answer.isdigit() and 1 <= int(answer) <= len(candidates):
                session.record(index, candidates[int(answer) - 1])
                break
            write("      unrecognised - type h for help")

    write(f"\nDone. {session.done}/{session.total} labelled.")
    return 0
