from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.retrieval.lm_retriever import LMRetriever

@dataclass
class ProcessedQuery:
    """Holds a processed query ready to be sent to a retriever."""

    original: str
    text: str  # text stripped of syntax
    tokens: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    expanded: bool = False  # was synonym expansion applied?

    def to_weights(self) -> dict[str, float]:
        """Convert the processed text into normalized query weights P(w|q)."""
        w: dict[str, float] = {}
        for q in self.tokens:
            w[q] = w.get(q, 0.0) + 1.0
        tot = sum(w.values())
        if tot > 0:
            for k in w:
                w[k] /= tot
        return w


class QueryProcessor:
    """
    Pre-processes user queries for the information retrieval system (SRI).

    Parameters
    ----------
    expand_synonyms : bool – expand with dynamic WordNet synonyms
                             (default True)
    """

    def __init__(self) -> None:
        pass

    def process(self, raw_query: str) -> ProcessedQuery:
        """
        Process *raw_query* and return a ProcessedQuery.

        Steps
        -----
        1. Normalise whitespace and casing
        2. Detect explicit filters (``source:xataka``)
        """
        query = self._clean(raw_query)
        filters: dict[str, str] = {}

        # Extracts filter prefixes
        text, filters = self._extract_filters(query)

        tokens = text.split()

        return ProcessedQuery(
            original=raw_query,
            text=text,
            tokens=tokens,
            filters=filters,
        )

    def apply_prf(
        self,
        orig_q_weights: dict[str, float],
        retriever: "LMRetriever",
        prf_k: int = 5,
        prf_terms: int = 10,
        prf_alpha: float = 0.5,
    ) -> dict[str, float]:
        """
        Calculate RM3 updated query weights using Pseudo-Relevance Feedback.

        Reference: Lavrenko & Croft (2001) - Relevance Based Language Models.
        """
        if not retriever.index:
            return orig_q_weights

        # Initial retrieval
        initial_results = retriever.retrieve(orig_q_weights, top_k=prf_k)
        if not initial_results:
            return orig_q_weights

        top_k_docs = [(r["id"], r["score"]) for r in initial_results]

        # Exponentiate scores to probabilities P(d|q)
        max_score = max(score for _, score in top_k_docs)
        doc_probs = {
            doc_id: math.exp(score - max_score) for doc_id, score in top_k_docs
        }

        sum_probs = sum(doc_probs.values())
        for d in doc_probs:
            doc_probs[d] /= sum_probs

        # Compute RM1: P(w|R) = sum_{d} P(w|d) * P(d|q)
        rm1_probs: dict[str, float] = {}
        idx = retriever.index._index
        doc_info = retriever.index._doc_info

        for doc_id, p_d_q in doc_probs.items():
            doc_len = doc_info[doc_id].get("length", 0)
            if doc_len == 0:
                continue

            # Iterate over all terms in the document to compute P(w|R)
            for w, postings in idx.items():
                if doc_id in postings:
                    p_w_d = postings[doc_id] / doc_len
                    rm1_probs[w] = rm1_probs.get(w, 0.0) + (p_w_d * p_d_q)

        rm1_sum = sum(rm1_probs.values())
        if rm1_sum > 0:
            for w in rm1_probs:
                rm1_probs[w] /= rm1_sum

        # Interpolate RM1 with the original query (RM3)
        rm3_probs: dict[str, float] = {}
        all_terms = set(orig_q_weights.keys()).union(set(rm1_probs.keys()))

        for w in all_terms:
            p_orig = orig_q_weights.get(w, 0.0)
            p_rm1 = rm1_probs.get(w, 0.0)
            rm3_probs[w] = (prf_alpha * p_orig) + ((1.0 - prf_alpha) * p_rm1)

        #  Select top `prf_terms` from RM3
        top_terms = sorted(rm3_probs.items(), key=lambda x: x[1], reverse=True)[
            :prf_terms
        ]

        # Re-normalize just the top terms
        final_weights = {}
        sum_top = sum(weight for _, weight in top_terms)
        if sum_top > 0:
            for w, weight in top_terms:
                final_weights[w] = weight / sum_top

        return final_weights

    @staticmethod
    def _clean(text: str) -> str:
        """Strip excess whitespace and lower-case."""
        return re.sub(r"\s+", " ", text.strip().lower())

    @staticmethod
    def _extract_filters(query: str) -> tuple[str, dict[str, str]]:
        """
        Extract key:value filter tokens from the query string.

        Example: "iphone 16 source:xataka"
            -> ("iphone 16", {"source": "xataka"})
        """
        filters: dict[str, str] = {}
        pattern = re.compile(r"(\w+):(\S+)")
        clean_parts = []

        for token in query.split():
            m = pattern.fullmatch(token)
            if m:
                filters[m.group(1)] = m.group(2)
            else:
                clean_parts.append(token)

        return " ".join(clean_parts).strip(), filters
