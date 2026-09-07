"""Stage 4 - resolve a raw source name to a canonical test, or abstain.

Four layers, in this order:

    0 exact       alias-index hit. Correct by construction, confidence 1.0.
    1 candidates  two rapidfuzz passes over every canonical surface form.
                  token_set_ratio generates, because it is word-order
                  invariant and that closes the large class of misses like
                  "lactate dehydrogenase ldh" against "LDH". WRatio then
                  *ranks*.

                  The split exists because token_set_ratio returns a flat 100
                  whenever one token set is a subset of the other, which tied
                  urea against bun at 100 apiece on "blood urea nitrogen bun".
                  token_sort_ratio fixes that but over-punishes elaboration,
                  scoring "esr automated westergren erythrocyte sedimentation
                  rate" against "esr" at 10. On a seven-case discrimination
                  set - each a raw name with one right and one plausibly wrong
                  surface - WRatio ranked 7/7 correctly, token_sort 6/7 and
                  token_set 4/7.
    2 veto        attribute conflicts between the raw name and the candidate,
                  plus the taxonomy's own declared-distinct rules. Runs after
                  scoring and unconditionally: a model that is 0.98 confident a
                  serum calcium is a urine calcium is still wrong.
    3 rerank      optional sentence-transformer cosine similarity over the
                  survivors. Optional on purpose - layers 0-2 are a working
                  matcher on their own and need no PyTorch.

Then abstain, on a low top score or a thin margin between the top two. For this
product "94% precision at 71% coverage, abstains on the rest" beats "88% at
100%": a wrong price shown confidently is worse than no price at all.

THRESHOLDS BELOW ARE UNTUNED PLACEHOLDERS. Phase 03 labels 500 pairs *before*
tuning anything and fits them on held-out data. Tuning them against the corpus
first would make the evaluation meaningless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from rapidfuzz import fuzz, process

from ratecard.names import normalise
from ratecard.normalise import rules
from ratecard.normalise.attributes import Attributes, conflicts, extract
from ratecard.taxonomy.loader import Taxonomy

# Untuned. See module docstring.
ACCEPT_THRESHOLD = 85.0
MARGIN = 5.0
# How much the embedding is allowed to move a candidate. Untuned.
RERANK_WEIGHT = 0.35
CANDIDATE_LIMIT = 10
CANDIDATE_FLOOR = 60.0

# A candidate must share at least one substantial word with the query. Not a
# tuned threshold - a structural guard. WRatio emits a flat 85.5 for certain
# partial alignments, which let pure noise through: "12 GENE PANEL (NGS)" tied
# iron_studies against lipid_profile at 85.5 apiece and abstained on a thin
# margin, when the truthful answer is that nothing in the taxonomy matches it
# at all. Requiring a shared word of 3+ characters removes that whole class
# without touching what counts as a good score.
MIN_SHARED_TOKEN = 3

# ...but the shared word has to actually mean something. "12 GENE PANEL (NGS)"
# survived the guard above by sharing "panel" with the alias "iron panel",
# which is no evidence at all. These words appear across every category and
# carry no identity, so they do not count as overlap. They are still visible to
# the scorer and to the attribute extractor - this list only governs what
# counts as grounds for considering a candidate in the first place.
GENERIC_TOKENS = frozenset({
    "panel", "profile", "screen", "screening", "test", "tests", "level",
    "levels", "serum", "blood", "plasma", "total", "count", "scan", "study",
    "quantitative", "qualitative", "random", "routine", "complete", "whole",
    "with", "and", "for", "single", "direct", "indirect", "automated",
})


@dataclass(frozen=True, slots=True)
class Candidate:
    test_id: str
    surface: str
    lexical: float
    rerank: float | None = None
    veto: str | None = None

    @property
    def score(self) -> float:
        """Blend, not replace.

        The rerank arrives as a cosine similarity scaled to 0-100, and those
        cluster tightly - a MiniLM embedding of two short medical phrases is
        rarely below 0.5 or above 0.95. Letting it *replace* the lexical score
        collapsed the spread between candidates, so nearly everything fell
        inside the thin-margin window and the matcher abstained on rows it had
        been resolving correctly: "blood urea nitrogen bun" and "serum
        electrolytes (na k cl)" both regressed to abstentions.

        Blending keeps the lexical spread and lets the embedding move a
        candidate up or down within it. RERANK_WEIGHT is untuned, like every
        other constant here.
        """
        if self.rerank is None:
            return self.lexical
        return (1.0 - RERANK_WEIGHT) * self.lexical + RERANK_WEIGHT * self.rerank

    @property
    def blocked(self) -> bool:
        return self.veto is not None


@dataclass(frozen=True, slots=True)
class Match:
    raw_name: str
    test_id: str | None
    confidence: float
    method: str
    reason: str | None = None
    candidates: tuple[Candidate, ...] = ()

    @property
    def abstained(self) -> bool:
        return self.test_id is None

    @property
    def needs_review(self) -> bool:
        """What Stage 5 writes into price_observation.needs_review."""
        return self.test_id is None or self.method != "exact" and self.confidence < 95.0


@dataclass
class Matcher:
    taxonomy: Taxonomy
    accept_threshold: float = ACCEPT_THRESHOLD
    margin: float = MARGIN
    candidate_limit: int = CANDIDATE_LIMIT
    candidate_floor: float = CANDIDATE_FLOOR
    reranker: object | None = field(default=None, repr=False)

    @cached_property
    def _surfaces(self) -> tuple[list[str], list[str]]:
        """Every normalised surface form, parallel to the test id it belongs to."""
        forms: list[str] = []
        owners: list[str] = []
        for test in self.taxonomy:
            for surface in (test.name, *test.aliases):
                key = normalise(surface)
                if key:
                    forms.append(key)
                    owners.append(test.id)
        return forms, owners

    # -- layer 1 ---------------------------------------------------------
    def candidates(self, raw_name: str) -> list[Candidate]:
        """Best-scoring surface form per canonical test, highest first.

        Generation and ranking use different scorers on purpose - see the
        module docstring. A candidate is kept on its token_sort score, so a
        canonical name that is merely *contained* in a long raw string no
        longer ties with the one that actually covers it.
        """
        query = normalise(raw_name)
        if not query:
            return []
        forms, owners = self._surfaces

        query_tokens = {
            t for t in query.split()
            if len(t) >= MIN_SHARED_TOKEN and t not in GENERIC_TOKENS
        }

        best: dict[str, Candidate] = {}
        for surface, _set_score, index in process.extract(
            query, forms, scorer=fuzz.token_set_ratio,
            limit=self.candidate_limit * 12, score_cutoff=self.candidate_floor,
        ):
            surface_tokens = {
                t for t in surface.split()
                if len(t) >= MIN_SHARED_TOKEN and t not in GENERIC_TOKENS
            }
            if query_tokens and surface_tokens and not (query_tokens & surface_tokens):
                continue
            score = fuzz.WRatio(query, surface)
            test_id = owners[index]
            if test_id not in best or score > best[test_id].lexical:
                best[test_id] = Candidate(test_id=test_id, surface=surface, lexical=score)

        return sorted(best.values(), key=lambda c: -c.lexical)[: self.candidate_limit]

    # -- layer 2 ---------------------------------------------------------
    def _apply_vetoes(self, raw_name: str, raw_attrs: Attributes,
                      candidates: list[Candidate]) -> list[Candidate]:
        """Mark candidates the raw name's own words rule out.

        Two sources of veto. The attribute comparison catches what the string
        says about itself ("plain", "urine", "free"). The taxonomy's
        declared_distinct catches pairs no string feature separates, by
        vetoing a lower candidate that a curator said differs from the leader.
        """
        out: list[Candidate] = []
        for candidate in candidates:
            test = self.taxonomy[candidate.test_id]
            attr_conflicts = conflicts(raw_attrs, test)
            veto = attr_conflicts[0].rule + ": " + attr_conflicts[0].detail if attr_conflicts else None
            out.append(Candidate(candidate.test_id, candidate.surface,
                                 candidate.lexical, candidate.rerank, veto))
        return out

    # -- layer 3 ---------------------------------------------------------
    def _rerank(self, raw_name: str, candidates: list[Candidate]) -> list[Candidate]:
        if self.reranker is None or not candidates:
            return candidates
        names = [self.taxonomy[c.test_id].name for c in candidates]
        scores = self.reranker.similarities(raw_name, names)  # 0..1
        return [
            Candidate(c.test_id, c.surface, c.lexical, float(s) * 100.0, c.veto)
            for c, s in zip(candidates, scores, strict=True)
        ]

    # -- orchestration ---------------------------------------------------
    def match(self, raw_name: str) -> Match:
        exact = self.taxonomy.lookup(raw_name)
        if exact is not None:
            return Match(raw_name, exact.id, 100.0, "exact")

        found = self.candidates(raw_name)
        if not found:
            return Match(raw_name, None, 0.0, "abstain_no_candidate",
                         "nothing scored above the candidate floor")

        raw_attrs = extract(raw_name)
        found = self._apply_vetoes(raw_name, raw_attrs, found)
        found = self._rerank(raw_name, found)
        found.sort(key=lambda c: -c.score)

        survivors = [c for c in found if not c.blocked]
        if not survivors:
            return Match(raw_name, None, 0.0, "abstain_vetoed",
                         f"every candidate blocked; best was {found[0].test_id} "
                         f"({found[0].veto})", tuple(found))

        top = survivors[0]
        if top.score < self.accept_threshold:
            return Match(raw_name, None, top.score, "abstain_low_score",
                         f"best candidate {top.test_id} scored {top.score:.1f} "
                         f"< {self.accept_threshold}", tuple(found))

        if len(survivors) > 1:
            second = survivors[1]
            if top.score - second.score < self.margin:
                declared = rules.blocks(self.taxonomy[top.test_id],
                                        self.taxonomy[second.test_id])
                note = "curated as distinct" if declared else "too close to separate"
                return Match(raw_name, None, top.score, "abstain_thin_margin",
                             f"{top.test_id} {top.score:.1f} vs {second.test_id} "
                             f"{second.score:.1f} - {note}", tuple(found))

        method = "lexical" if top.rerank is None else "embedding"
        return Match(raw_name, top.test_id, top.score, method, None, tuple(found))

    def match_many(self, raw_names) -> list[Match]:
        return [self.match(name) for name in raw_names]
