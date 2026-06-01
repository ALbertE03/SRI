
from typing import Dict, List, Optional
from src.indexing.indexer import TextNormalizer
from src.utils.logger import get_logger

logger = get_logger("RocchioFeedback")


class RocchioFeedback:
    """
    Rocchio algorithm for relevance feedback.

    Q_new = alpha * Q_orig + beta * mean(D_rel) - gamma * mean(D_nonrel)

    Parameters
    ----------
    normalizer : TextNormalizer
        Text normalizer for tokenizing documents.
    alpha : float
        Weight for original query.
    beta : float
        Weight for relevant documents.
    gamma : float
        Weight for non-relevant documents.
    clip_below : float
        Clamp negative weights to 0 and remove terms below this threshold.
    """

    def __init__(
        self,
        normalizer: Optional[TextNormalizer] = None,
        alpha: float = 1.0,
        beta: float = 0.75,
        gamma: float = 0.15,
        clip_below: float = 1e-4,
    ):
        self.normalizer = normalizer or TextNormalizer()
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.clip_below = clip_below
    def __str__(self) -> str:
        return f"RocchioFeedback (alpha={self.alpha}, beta={self.beta}, gamma={self.gamma})"
    def _term_vector(self, text: str) -> Dict[str, float]:
        """Convert text to TF-weighted term vector."""
        tokens = self.normalizer.normalize_query(text)
        vec: Dict[str, float] = {}
        for t in tokens:
            vec[t] = vec.get(t, 0.0) + 1.0
        length = sum(vec.values())
        if length > 0:
            for t in vec:
                vec[t] /= length
        return vec

    def reformulate(
        self,
        original_query: str,
        relevant_docs: List[str],
        non_relevant_docs: List[str],
    ) -> Dict[str, float]:
        """
        Apply Rocchio feedback to produce a new set of query weights.

        Parameters
        ----------
        original_query : str
            The original query text.
        relevant_docs : list of str
            Document texts marked as relevant.
        non_relevant_docs : list of str
            Document texts marked as non-relevant.

        Returns
        -------
        dict of {term: weight}
        """
        q_vec = self._term_vector(original_query)

        rel_vec: Dict[str, float] = {}
        if relevant_docs:
            for doc_text in relevant_docs:
                doc_vec = self._term_vector(doc_text)
                for term, w in doc_vec.items():
                    rel_vec[term] = rel_vec.get(term, 0.0) + w
            n_rel = len(relevant_docs)
            for term in rel_vec:
                rel_vec[term] /= n_rel

        nonrel_vec: Dict[str, float] = {}
        if non_relevant_docs:
            for doc_text in non_relevant_docs:
                doc_vec = self._term_vector(doc_text)
                for term, w in doc_vec.items():
                    nonrel_vec[term] = nonrel_vec.get(term, 0.0) + w
            n_nonrel = len(non_relevant_docs)
            for term in nonrel_vec:
                nonrel_vec[term] /= n_nonrel

        all_terms = set(q_vec.keys()) | set(rel_vec.keys()) | set(nonrel_vec.keys())
        new_weights: Dict[str, float] = {}
        for term in all_terms:
            w = (self.alpha * q_vec.get(term, 0.0)
                 + self.beta * rel_vec.get(term, 0.0)
                 - self.gamma * nonrel_vec.get(term, 0.0))
            if w > self.clip_below:
                new_weights[term] = w

        total = sum(new_weights.values())
        if total > 0:
            for t in new_weights:
                new_weights[t] /= total

        logger.info(f"Rocchio: query expanded from {len(q_vec)} to {len(new_weights)} terms")
        if relevant_docs:
            logger.info(f"  + {len(relevant_docs)} relevant docs (beta={self.beta})")
        if non_relevant_docs:
            logger.info(f"  - {len(non_relevant_docs)} non-relevant docs (gamma={self.gamma})")

        return new_weights
