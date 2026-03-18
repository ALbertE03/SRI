from __future__ import annotations

import re
from dataclasses import dataclass, field

import nltk
from nltk.corpus import wordnet

try:
    wordnet.synsets("prueba", lang="spa")
except LookupError:
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)


def _get_spanish_synonyms(word: str, max_synonyms: int = 5) -> list[str]:
    """
    Retrieve Spanish synonyms for *word* using WordNet.

    Looks up synsets for the term in Spanish and collects the Spanish
    lemmas from each synset found, excluding the original term itself.
    """
    synonyms: list[str] = []
    seen: set[str] = set()

    for syn in wordnet.synsets(word, lang="spa"):
        for lemma in syn.lemmas(lang="spa"):
            name = lemma.name().replace("_", " ").lower()
            if name != word.lower() and name not in seen:
                seen.add(name)
                synonyms.append(name)
                if len(synonyms) >= max_synonyms:
                    return synonyms
    return synonyms


@dataclass
class ProcessedQuery:
    """Holds a processed query ready to be sent to a retriever."""

    original: str
    text: str  # expanded / normalised text
    tokens: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    expanded: bool = False  # was synonym expansion applied?


class QueryProcessor:
    """
    Pre-processes user queries for the information retrieval system (SRI).

    Parameters
    ----------
    expand_synonyms : bool – expand with dynamic WordNet synonyms
                             (default True)
    """

    def __init__(
        self,
        expand_synonyms: bool = True,
    ) -> None:
        self.expand_synonyms = expand_synonyms

    def process(self, raw_query: str) -> ProcessedQuery:
        """
        Process *raw_query* and return a ProcessedQuery.

        Steps
        -----
        1. Normalise whitespace and casing
        2. Detect explicit filters (``source:xataka``)
        3. Optionally expand with Spanish WordNet synonyms
        """
        query = self._clean(raw_query)
        filters: dict[str, str] = {}

        #   Explicit filter extraction
        query, filters = self._extract_filters(query)

        # Synonym expansion
        expanded = False
        text = query
        if self.expand_synonyms:
            text, expanded = self._expand(query)

        tokens = text.split()

        return ProcessedQuery(
            original=raw_query,
            text=text,
            tokens=tokens,
            filters=filters,
            expanded=expanded,
        )

    @staticmethod
    def rerank_by_date(results: list[dict], descending: bool = True) -> list[dict]:
        """Re-rank results by publication date (most recent first by default)."""

        def _date_key(r: dict) -> str:
            return r.get("date") or ""

        return sorted(results, key=_date_key, reverse=descending)

    @staticmethod
    def rerank_mmr(
        results: list[dict],
        top_k: int = 10,
        diversity: float = 0.3,
    ) -> list[dict]:
        """
        Maximal Marginal Relevance (MMR) re-ranking.

        Balances relevance and diversity by penalising results that share
        many tags or the same brand as already-selected results.

        Parameters
        ----------
        results   : ranked list from a retriever
        top_k     : output size
        diversity : weight of the diversity term (0 = pure relevance)
        """
        if not results:
            return []

        selected: list[dict] = []
        remaining: list[dict] = list(results)

        while remaining and len(selected) < top_k:
            if not selected:
                # First pick: highest-ranked
                selected.append(remaining.pop(0))
                continue

            # Compute MMR score for each candidate
            best_item = None
            best_score = float("-inf")

            for idx, candidate in enumerate(remaining):
                # Relevance proxy: inverse of position in original list
                rel = 1.0 / (results.index(candidate) + 1)

                # Diversity: max similarity to any already-selected doc
                sim = max(_jaccard_tags(candidate, sel) for sel in selected)

                mmr = (1 - diversity) * rel - diversity * sim
                if mmr > best_score:
                    best_score = mmr
                    best_item = (idx, candidate)

            if best_item is None:
                break
            idx, item = best_item
            selected.append(remaining.pop(idx))

        return selected

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

    @staticmethod
    def _expand(query: str) -> tuple[str, bool]:
        """
        Expand *query* by appending Spanish synonyms obtained
        dynamically from WordNet.
        """
        tokens = query.split()
        additions: list[str] = []
        expanded = False

        for token in tokens:
            syns = _get_spanish_synonyms(token)
            for s in syns:
                if s not in query and s not in additions:
                    additions.append(s)
                    expanded = True

        if additions:
            return query + " " + " ".join(additions), expanded
        return query, False


def _jaccard_tags(a: dict, b: dict) -> float:
    """Jaccard similarity between the tag sets of two documents."""
    ta = set(a.get("tags", []) or [])
    tb = set(b.get("tags", []) or [])
    if not ta and not tb:
        # Fall back to brand similarity
        return 1.0 if a.get("brand") == b.get("brand") and a.get("brand") else 0.0
    union = ta | tb
    if not union:
        return 0.0
    return len(ta & tb) / len(union)
