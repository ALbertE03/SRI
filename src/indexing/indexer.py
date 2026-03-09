"""
Inverted index + text normalization for the SRI project.

TextNormalizer
    Handles tokenization, stop-word removal and stemming for Spanish/English.
    Uses NLTK under the hood; downloads corpora on first use.

InvertedIndex
    Builds an inverted index from a list of documents.
    Supports TF-IDF weighted posting lists and BM25-compatible statistics.
    Can be persisted to / loaded from disk (JSON + pickle).

Typical usage
-------------
    from src.indexing import InvertedIndex, TextNormalizer

    norm = TextNormalizer()
    idx  = InvertedIndex(normalizer=norm)
    idx.build(docs)          # docs: list[dict] each with "id" and "content" keys
    idx.save("indexes/")
    results = idx.search("iPhone 16 Pro camera", top_k=10)
"""

from __future__ import annotations

import json
import math
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path
import nltk

# ---------------------------------------------------------------------------
# Ensure required NLTK data is available
# ---------------------------------------------------------------------------

def _ensure_nltk() -> None:
    datasets = [
        ("tokenizers/punkt_tab", "punkt_tab"),
        ("corpora/stopwords", "stopwords"),
    ]
    for resource_path, download_id in datasets:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            nltk.download(download_id, quiet=True)


_ensure_nltk()

from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from nltk.tokenize import word_tokenize


# ---------------------------------------------------------------------------
# Stop-words: Spanish + English (content is bilingual)
# ---------------------------------------------------------------------------
_STOP_WORDS: frozenset[str] = frozenset(
    stopwords.words("spanish") + stopwords.words("english")
)

# ---------------------------------------------------------------------------
# TextNormalizer
# ---------------------------------------------------------------------------


class TextNormalizer:
    """
    Converts raw text into a list of normalised tokens.

    Pipeline
    --------
    1. Lowercase
    2. Remove URLs, HTML remnants and non-alphanumeric characters
    3. Tokenize (NLTK punkt)
    4. Remove stop-words (es + en)
    5. Stem (SnowballStemmer — Spanish by default; falls back to English)
    """

    def __init__(self, language: str = "spanish") -> None:
        self.language = language
        self._stemmer = SnowballStemmer(language)

    # ------------------------------------------------------------------
    def normalize(self, text: str) -> list[str]:
        """Return a list of normalised tokens from *text*."""
        if not text:
            return []

        # lowercase
        text = text.lower()

        # strip URLs
        text = re.sub(r"https?://\S+|www\.\S+", " ", text)

        # strip non-alphanumeric (keep letters, digits and spaces)
        text = re.sub(r"[^a-záéíóúüñ\w\s]", " ", text, flags=re.UNICODE)

        # tokenize
        tokens = word_tokenize(text, language="spanish")

        #filter stop-words and short tokens
        tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]

        

        return tokens

    def normalize_query(self, query: str) -> list[str]:
        """Normalise a user query (same pipeline as document tokens)."""
        return self.normalize(query)


# ---------------------------------------------------------------------------
# InvertedIndex
# ---------------------------------------------------------------------------


class InvertedIndex:
    """
    Inverted index with TF-IDF document vectors.

    Internal data structures
    ------------------------
    _index     : dict[term, dict[doc_id, tf]]
                 Posting list: term → {doc_id: raw term frequency}
    _doc_info  : dict[doc_id, {"length": int, "norm": float}]
                 Per-document statistics used during scoring
    _vocab     : set[str]   – all indexed terms
    _N         : int        – total number of documents indexed

    Parameters 
    -----------------
    k1 : float  – term-frequency saturation (default 1.5)
    b  : float  – document-length normalisation (default 0.75)
    """

    INDEX_FILE = "inverted_index.pkl"
    META_FILE  = "index_meta.json"

    def __init__(
        self,
        normalizer: TextNormalizer | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.normalizer = normalizer or TextNormalizer()
        self.k1 = k1
        self.b  = b

        # Core structures
        self._index: dict[str, dict[str, int]] = defaultdict(dict)
        self._doc_info: dict[str, dict] = {}
        self._doc_lengths: dict[str, int] = {}
        self._N: int = 0
        self._avg_dl: float = 0.0
        self._vocab: set[str] = set()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, documents: list[dict]) -> None:
        """
        Build the index from *documents*.

        Each document must have:
            - "id"      : str – unique identifier
            - "content" : str – main text to index
            - "title"   : str (optional) – boosted at index time
        """
        self._index    = defaultdict(dict)
        self._doc_info = {}
        self._N        = 0

        for doc in documents:
            doc_id  = str(doc.get("id") or doc.get("url", ""))
            title   = doc.get("title", "") or ""
            content = doc.get("content", "") or ""

            # Title tokens are repeated 3× to boost title importance
            text = title + " " + (title + " ") * 2 + content
            tokens = self.normalizer.normalize(text)

            if not tokens:
                continue

            tf = Counter(tokens)
            doc_length = len(tokens)

            for term, count in tf.items():
                self._index[term][doc_id] = count

            self._doc_info[doc_id] = {
                "length":  doc_length,
                "title":   title,
                "url":     doc.get("url", ""),
                "source":  doc.get("source", ""),
                "date":    doc.get("date", ""),
                "tags":    doc.get("tags", []),
                "category": doc.get("category", ""),
            }
            self._N += 1

        self._avg_dl = (
            sum(info["length"] for info in self._doc_info.values()) / self._N
            if self._N
            else 1.0
        )
        self._vocab = set(self._index.keys())

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        category_filter: str | None = None,
    ) -> list[dict]:
        """
        Score documents with BM25 and return the *top_k* results.

        Parameters
        ----------
        query          : free-text user query
        top_k          : maximum number of results to return
        category_filter: if given, restrict results to this category
                         (e.g. "mobile", "pc")

        Returns
        -------
        list of dicts with keys: doc_id, score, title, url, source, date, tags
        """
        q_terms = self.normalizer.normalize_query(query)
        if not q_terms:
            return []

        scores: dict[str, float] = defaultdict(float)

        for term in q_terms:
            if term not in self._index:
                continue

            postings = self._index[term]
            df       = len(postings)
            idf      = math.log((self._N - df + 0.5) / (df + 0.5) + 1)

            for doc_id, tf in postings.items():
                dl  = self._doc_info[doc_id]["length"]
                tf_norm = (
                    tf * (self.k1 + 1)
                ) / (
                    tf + self.k1 * (1 - self.b + self.b * dl / self._avg_dl)
                )
                scores[doc_id] += idf * tf_norm

        # Apply category filter
        if category_filter:
            scores = {
                doc_id: score
                for doc_id, score in scores.items()
                if self._doc_info.get(doc_id, {}).get("category", "")
                   == category_filter
            }

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for doc_id, score in ranked:
            info = self._doc_info.get(doc_id, {})
            results.append(
                {
                    "doc_id": doc_id,
                    "score":  round(score, 6),
                    "title":  info.get("title", ""),
                    "url":    info.get("url", doc_id),
                    "source": info.get("source", ""),
                    "date":   info.get("date", ""),
                    "tags":   info.get("tags", []),
                    "category": info.get("category", ""),
                }
            )
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Persist the index to *directory* (created if absent)."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        # Pickle the posting lists (faster I/O than JSON for large data)
        with open(path / self.INDEX_FILE, "wb") as fh:
            pickle.dump(
                {
                    "index":    dict(self._index),
                    "doc_info": self._doc_info,
                    "N":        self._N,
                    "avg_dl":   self._avg_dl,
                    "k1":       self.k1,
                    "b":        self.b,
                },
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        # Human-readable metadata summary
        meta = {
            "num_documents":  self._N,
            "vocabulary_size": len(self._vocab),
            "avg_doc_length":  round(self._avg_dl, 2),
            "k1": self.k1,
            "b":  self.b,
        }
        with open(path / self.META_FILE, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2, ensure_ascii=False)

        print(
            f"[InvertedIndex] Saved: {self._N} docs, "
            f"{len(self._vocab)} terms → {path}"
        )

    @classmethod
    def load(cls, directory: str | Path) -> "InvertedIndex":
        """Load a previously saved index from *directory*."""
        path = Path(directory)
        with open(path / cls.INDEX_FILE, "rb") as fh:
            data = pickle.load(fh)

        idx = cls(k1=data["k1"], b=data["b"])
        idx._index    = defaultdict(dict, data["index"])
        idx._doc_info = data["doc_info"]
        idx._N        = data["N"]
        idx._avg_dl   = data["avg_dl"]
        idx._vocab    = set(idx._index.keys())
        return idx

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"InvertedIndex(docs={self._N}, "
            f"vocab={len(self._vocab)}, "
            f"k1={self.k1}, b={self.b})"
        )

    def stats(self) -> dict:
        """Return a summary dict of index statistics."""
        return {
            "num_documents":   self._N,
            "vocabulary_size": len(self._vocab),
            "avg_doc_length":  round(self._avg_dl, 2),
            "k1": self.k1,
            "b":  self.b,
        }
