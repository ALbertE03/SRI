from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Domain synonym dictionary (Spanish ↔ English, tech terms)
# ---------------------------------------------------------------------------

_SYNONYMS: dict[str, list[str]] = {
    # Mobile
    "móvil":          ["smartphone", "teléfono", "celular", "phone"],
    "movil":          ["smartphone", "telefono", "celular", "phone"],
    "smartphone":     ["móvil", "teléfono", "phone"],
    "teléfono":       ["móvil", "smartphone", "phone"],
    "telefono":       ["movil", "smartphone", "phone"],

    # PC / Computer
    "portátil":       ["laptop", "notebook", "ordenador portátil"],
    "portatil":       ["laptop", "notebook"],
    "laptop":         ["portátil", "notebook", "ordenador portátil"],
    "ordenador":      ["computadora", "pc", "computer"],
    "computadora":    ["ordenador", "pc", "computer"],
    "pc":             ["ordenador", "computadora", "desktop"],

    # Reviews / articles
    "análisis":       ["review", "prueba", "test", "reseña"],
    "analisis":       ["review", "prueba", "test", "resena"],
    "review":         ["análisis", "prueba", "reseña", "test"],
    "comparativa":    ["comparison", "versus", "vs"],
    "comparison":     ["comparativa", "versus"],

    # Common specs
    "batería":        ["battery", "autonomia", "autonomía"],
    "bateria":        ["battery", "autonomia"],
    "cámara":         ["camera", "foto", "fotografía"],
    "camara":         ["camera", "foto", "fotografia"],
    "pantalla":       ["screen", "display", "monitor"],
    "procesador":     ["cpu", "chip", "processor"],
    "memoria":        ["ram", "memory"],
    "almacenamiento": ["storage", "ssd", "disco"],
    "rendimiento":    ["performance", "benchmark", "velocidad"],

    # Brands common aliases
    "apple":          ["iphone", "ipad", "mac", "ios"],
    "samsung":        ["galaxy", "one ui"],
    "google":         ["pixel", "android"],
}

# Category hints: if these words appear in the query, infer a category
_CATEGORY_HINTS: dict[str, list[str]] = {
    "mobile": [
        "móvil", "movil", "smartphone", "iphone", "samsung galaxy",
        "android", "ios", "teléfono", "telefono", "celular", "phone",
        "apple watch", "watch", "airpods", "ipad",
    ],
    "pc": [
        "laptop", "portátil", "portatil", "ordenador", "computadora",
        "windows", "mac", "linux", "gaming pc", "desktop", "monitor",
        "gpu", "cpu", "tarjeta gráfica", "procesador",
        "ssd", "motherboard", "placa base",
    ],
}


# ---------------------------------------------------------------------------
# ProcessedQuery
# ---------------------------------------------------------------------------

@dataclass
class ProcessedQuery:
    """Holds a processed query ready to be sent to a retriever."""

    original:  str
    text:      str                      # expanded / normalised text
    tokens:    list[str] = field(default_factory=list)
    category:  str | None = None        # inferred or explicit category filter
    filters:   dict[str, str] = field(default_factory=dict)
    expanded:  bool = False             # was synonym expansion applied?


# ---------------------------------------------------------------------------
# QueryProcessor
# ---------------------------------------------------------------------------


class QueryProcessor:
    """
    Pre-processes user queries for the SRI tech-news retrieval system.

    Parameters
    ----------
    expand_synonyms : bool  – whether to expand with domain synonyms (default True)
    infer_category  : bool  – whether to auto-detect category from keywords
    """

    def __init__(
        self,
        expand_synonyms: bool = True,
        infer_category:  bool = True,
    ) -> None:
        self.expand_synonyms = expand_synonyms
        self.infer_category  = infer_category

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, raw_query: str) -> ProcessedQuery:
        """
        Process *raw_query* and return a ProcessedQuery.

        Steps
        -----
        1. Normalize whitespace and casing
        2. Detect explicit filters (``category:mobile``)
        3. Infer implicit category from vocabulary
        4. Optionally expand with synonyms
        """
        query = self._clean(raw_query)
        filters: dict[str, str] = {}

        # --- 1. Explicit filter extraction ------------------------------------
        # Syntax: "query text category:mobile" or "query text source:xataka"
        query, filters = self._extract_filters(query)

        # --- 2. Category inference -------------------------------------------
        category = filters.pop("category", None)
        if category is None and self.infer_category:
            category = self._infer_category(query)

        # --- 3. Synonym expansion --------------------------------------------
        expanded = False
        text = query
        if self.expand_synonyms:
            text, expanded = self._expand(query)

        tokens = text.split()

        return ProcessedQuery(
            original  = raw_query,
            text      = text,
            tokens    = tokens,
            category  = category,
            filters   = filters,
            expanded  = expanded,
        )

    # ------------------------------------------------------------------
    # Post-processing / re-ranking
    # ------------------------------------------------------------------

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
        Maximal Marginal Relevance re-ranking.

        Balances relevance and diversity by penalising results that share
        many tags or the same brand as already-selected results.

        Parameters
        ----------
        results   : ranked list from a retriever (must have "score" or rank)
        top_k     : output size
        diversity : weight of the diversity term (0 = pure relevance)
        """
        if not results:
            return []

        selected: list[dict]   = []
        remaining: list[dict]  = list(results)

        while remaining and len(selected) < top_k:
            if not selected:
                # First pick: highest-ranked
                selected.append(remaining.pop(0))
                continue

            # Compute MMR score for each candidate
            best_item  = None
            best_score = float("-inf")

            for idx, candidate in enumerate(remaining):
                # Relevance proxy: inverse of position in original list
                rel = 1.0 / (results.index(candidate) + 1)

                # Diversity: max similarity to any already-selected doc
                sim = max(
                    _jaccard_tags(candidate, sel) for sel in selected
                )

                mmr = (1 - diversity) * rel - diversity * sim
                if mmr > best_score:
                    best_score = mmr
                    best_item  = (idx, candidate)

            if best_item is None:
                break
            idx, item = best_item
            selected.append(remaining.pop(idx))

        return selected

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:
        """Strip excess whitespace and lower-case."""
        return re.sub(r"\s+", " ", text.strip().lower())

    @staticmethod
    def _extract_filters(query: str) -> tuple[str, dict[str, str]]:
        """
        Extract key:value filter tokens from the query string.

        Example: "iphone 16 category:mobile source:xataka"
            → ("iphone 16", {"category": "mobile", "source": "xataka"})
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
    def _infer_category(query: str) -> str | None:
        """Return a category string if strong hints are found in *query*."""
        q_lower = query.lower()
        scores: dict[str, int] = {cat: 0 for cat in _CATEGORY_HINTS}

        for cat, hints in _CATEGORY_HINTS.items():
            for hint in hints:
                if hint in q_lower:
                    scores[cat] += 1

        best_cat  = max(scores, key=lambda c: scores[c])
        best_score = scores[best_cat]
        return best_cat if best_score > 0 else None

    @staticmethod
    def _expand(query: str) -> tuple[str, bool]:
        """Append synonyms to *query* for recall improvement."""
        tokens    = query.split()
        additions: list[str] = []
        expanded  = False

        for token in tokens:
            syns = _SYNONYMS.get(token, [])
            for s in syns:
                if s not in query and s not in additions:
                    additions.append(s)
                    expanded = True

        if additions:
            return query + " " + " ".join(additions), expanded
        return query, False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
