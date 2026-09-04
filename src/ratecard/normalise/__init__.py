"""Stage 4 - resolve messy source names to the canonical taxonomy.

Phase 01 ships the rule layer only. It answers "may these two ever be the same
test?" using taxonomy structure alone, with no similarity scoring involved.

Phase 02 adds the two scoring passes underneath it:

    candidates -> rapidfuzz token-set ratio, top 10
    rerank     -> sentence-transformer cosine similarity
    veto       -> rules.blocks(), applied last and unconditionally
    abstain    -> low top score, or a thin margin between the top two

The veto runs last on purpose. A model that is 0.98 confident that a serum
calcium is a urine calcium is still wrong, and no threshold tuning fixes that.
"""

from ratecard.normalise.rules import advisories, blocks, explain

__all__ = ["advisories", "blocks", "explain"]
