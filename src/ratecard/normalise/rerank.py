"""Optional layer 3: rerank surviving candidates by meaning rather than spelling.

Deliberately isolated behind a tiny interface (`similarities`) and imported
lazily, because it is the only part of the project that needs PyTorch. Layers
0-2 of the matcher are a working system without it, and on a machine with no
NVIDIA card the default torch wheel costs ~3GB of CUDA libraries that never
run. `pip install ratecard[rerank]` with the CPU index is the intended route -
see pyproject.

Where this earns its keep is the class of name lexical scoring cannot reach:

    "esr automated westergren erythrocyte sedimentation rate" -> esr
    "sugar f"                                                 -> glucose_fasting

Neither shares enough surface with its canonical name for token overlap to
carry it, and both are unambiguous to a human reading the words.
"""

from __future__ import annotations

from functools import cached_property

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class RerankerUnavailable(RuntimeError):
    """sentence-transformers is not installed."""


class SentenceTransformerReranker:
    """Cosine similarity between a raw name and each candidate's canonical name.

    The model is loaded on first use, not on construction, so building a
    Matcher with a reranker attached stays cheap in tests and in the CLI's
    non-matching subcommands.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name

    @cached_property
    def _model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RerankerUnavailable(
                "sentence-transformers is not installed. Layers 0-2 of the "
                "matcher work without it; to enable this one:\n"
                "  pip install --index-url https://download.pytorch.org/whl/cpu "
                "--extra-index-url https://pypi.org/simple torch sentence-transformers"
            ) from exc
        return SentenceTransformer(self.model_name)

    def similarities(self, query: str, candidates: list[str]) -> list[float]:
        """Cosine similarity of `query` against each candidate, in 0..1."""
        if not candidates:
            return []
        model = self._model
        embeddings = model.encode([query, *candidates], normalize_embeddings=True)
        query_vector, candidate_vectors = embeddings[0], embeddings[1:]
        return [float(vector @ query_vector) for vector in candidate_vectors]


def load_reranker(model_name: str = DEFAULT_MODEL) -> SentenceTransformerReranker | None:
    """Return a reranker, or None when the optional dependency is absent.

    Callers treat None as "run lexical only" rather than as an error - a
    missing optional dependency should degrade the matcher, not break it.
    """
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return None
    return SentenceTransformerReranker(model_name)
