from __future__ import annotations

import math
import pickle
from pathlib import Path

from src.indexing.indexer import InvertedIndex, TextNormalizer


class LMRetriever:
    """
    retriever using the Probabilistic Language Model (LM)
    with Dirichlet Prior Smoothing.

    Reference:
    Zhai, C., & Lafferty, J. (2001). "A study of smoothing methods for
    language models applied to Ad Hoc information retrieval".

    Parameters
    ----------
    index : InvertedIndex | None
        The underlying inverted index containing term and collection frequencies.
    normalizer : TextNormalizer | None
        Shared text normaliser.
    mu : float
        Dirichlet smoothing parameter.
    """

    MODEL_FILE = "lm_model.pkl"

    def __init__(
        self,
        index: InvertedIndex | None = None,
        normalizer: TextNormalizer | None = None,
        mu: float = 2000.0,
    ) -> None:
        self.index = index
        self.normalizer = normalizer or TextNormalizer()
        self.mu = mu

        self._total_tokens_in_collection = 0
        self._collection_probs: dict[str, float] = {}

        if self.index is not None:
            self._precompute_collection_stats()

    @classmethod
    def from_inverted_index(
        cls,
        index: InvertedIndex,
        mu: float = 2000.0,
    ) -> "LMRetriever":
        """
        Build a Language Model retriever system from an InvertedIndex.
        """
        print(
            f"[LMRetriever] Initialising Language Model with Dirichlet Smoothing (μ={mu})..."
        )
        return cls(index=index, normalizer=index.normalizer, mu=mu)

    def _precompute_collection_stats(self) -> None:
        """Calculate total tokens in collection and term collection probabilities."""
        if not self.index:
            return

        # Total tokens in collection = sum of all document lengths
        self._total_tokens_in_collection = sum(
            info.get("length", 0) for info in self.index._doc_info.values()
        )

        if self._total_tokens_in_collection == 0:
            return

        # P(t|C) = cf(t) / |C|
        for term, postings in self.index._index.items():
            cf_t = sum(postings.values())
            self._collection_probs[term] = cf_t / self._total_tokens_in_collection

    def retrieve(
        self,
        query: str | dict[str, float],
        top_k: int = 10,
        category_filter: str | None = None,
    ) -> list[dict]:
        """
        Search and rank documents using Query Likelihood with Dirichlet Smoothing.
        Accepts either a raw string query or a dictionary of `{term: weight}`.
        """
        if self.index is None:
            raise RuntimeError("LMRetriever not initialised with an InvertedIndex.")

        q_weights: dict[str, float] = {}

        if isinstance(query, str):
            query_tokens = self.normalizer.normalize_query(query)
            if not query_tokens:
                return []
            for q in query_tokens:
                q_weights[q] = q_weights.get(q, 0.0) + 1.0

            # Normalize original query weights
            q_norm = sum(q_weights.values())
            for q in q_weights:
                q_weights[q] /= q_norm
        else:
            q_weights = query
            if not q_weights:
                return []

        #  Retrieval Pass
        doc_scores = self._score_documents(q_weights, category_filter)

        # Rank documents by highest score
        ranked_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        ranked_docs = ranked_docs[:top_k]

        results = []
        for doc_id, score in ranked_docs:
            doc_info = self.index._doc_info[doc_id]

            result_dict = doc_info.copy()
            result_dict["id"] = doc_id
            result_dict["score"] = score
            results.append(result_dict)

        return results

    def _score_documents(
        self, q_weights: dict[str, float], category_filter: str | None
    ) -> dict[str, float]:
        """Core scoring function (KL-divergence between query model and doc models)."""
        doc_scores: dict[str, float] = {}

        candidate_docs = set()
        for q in q_weights.keys():
            if q in self.index._index:
                candidate_docs.update(self.index._index[q].keys())

        # Filter by category if requested
        if category_filter:
            candidate_docs = {
                d
                for d in candidate_docs
                if self.index._doc_info[d].get("category") == category_filter
            }

        for doc_id in candidate_docs:
            doc_len = self.index._doc_info[doc_id].get("length", 0)
            score = 0.0

            for q, weight in q_weights.items():
                # Term Frequency in Document
                f_qd = self.index._index.get(q, {}).get(doc_id, 0)
                # Collection Probability
                p_qC = self._collection_probs.get(q, 1e-9)  # Small epsilon if unseen

                # Dirichlet smoothed probability:
                # P(q|d) = (f_qd + μ * P(q|C)) / (|d| + μ)
                prob = (f_qd + self.mu * p_qC) / (doc_len + self.mu)

                # Log probability weighted by term weight in query
                score += weight * math.log(prob)

            doc_scores[doc_id] = score

        return doc_scores

    def save(self, directory: str | Path) -> None:
        """Persist the retriever state and its components."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        state = {
            "index": self.index,
            "normalizer": self.normalizer,
            "mu": self.mu,
            "_total_tokens_in_collection": self._total_tokens_in_collection,
            "_collection_probs": self._collection_probs,
        }
        with open(path / self.MODEL_FILE, "wb") as fh:
            pickle.dump(state, fh, protocol=pickle.HIGHEST_PROTOCOL)

        print(f"[LMRetriever] Saved to {directory}")

    @classmethod
    def load(cls, directory: str | Path) -> "LMRetriever":
        """Load a persisted retriever from a directory."""
        path = Path(directory)
        model_path = path / cls.MODEL_FILE

        if not model_path.exists():
            raise FileNotFoundError(f"Missing language model file at {model_path}")

        with open(model_path, "rb") as fh:
            state = pickle.load(fh)

        retriever = cls(
            index=state.get("index"),
            normalizer=state.get("normalizer"),
            mu=state.get("mu", 2000.0),
        )
        retriever._total_tokens_in_collection = state.get(
            "_total_tokens_in_collection", 0
        )
        retriever._collection_probs = state.get("_collection_probs", {})

        return retriever

    def stats(self) -> dict:
        """Return combined statistics of the system."""
        if self.index:
            return self.index.stats()
        return {}

    def __repr__(self) -> str:
        num_docs = self.index._N if self.index else 0
        return f"LMRetriever(docs={num_docs}, mu={self.mu})"
