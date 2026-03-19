from __future__ import annotations

import json
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path
import nltk


def _ensure_nltk() -> None:
    """Ensure required NLTK data is available"""
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


# Stop-words: Spanish

_STOP_WORDS: frozenset[str] = frozenset(stopwords.words("spanish"))


class TextNormalizer:
    """
    Converts raw text into a list of normalised tokens.

    Pipeline
    --------
    1. Lowercase
    2. Remove URLs, HTML remnants and non-alphanumeric characters
    3. Tokenize (NLTK punkt)
    4. Remove stop-words (es)
    """

    def __init__(self, language: str = "spanish") -> None:
        self.language = language
        self._stemmer = SnowballStemmer(language)

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

        # filter stop-words and short tokens
        tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]

        return tokens

    def normalize_query(self, query: str) -> list[str]:
        """Normalise a user query (same pipeline as document tokens)."""
        return self.normalize(query)


class InvertedIndex:
    """
    Inverted index with TF-IDF document vectors.

    Internal data structures
    ------------------------
    _index     : dict[term, dict[doc_id, tf]]
                 Posting list: term → {doc_id: raw term frequency}
    _doc_info  : dict[doc_id, dict]
                 Per-document metadata (length, title, url, …)
    _vocab     : set[str]    all indexed terms
    _N         : int         total number of documents indexed
    """

    INDEX_FILE = "inverted_index.pkl"
    META_FILE = "index_meta.json"

    def __init__(
        self,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self.normalizer = normalizer or TextNormalizer()

        self._index: dict[str, dict[str, int]] = defaultdict(dict)
        self._doc_info: dict[str, dict] = {}
        self._N: int = 0
        self._vocab: set[str] = set()

    def build(self, documents: list[dict]) -> None:
        """
        Build the index from *documents*.

        Each document must have:
            - "id"      : str – unique identifier
            - "content" : str – main text to index
            - "title"   : str (optional) – boosted at index time
        """
        self._index = defaultdict(dict)
        self._doc_info = {}
        self._N = 0

        for doc in documents:
            doc_id = str(doc.get("id") or doc.get("url", ""))
            title = doc.get("title", "") or ""
            content = doc.get("content", "") or ""

            text = title + " " + content
            tokens = self.normalizer.normalize(text)

            if not tokens:
                continue

            tf = Counter(tokens)
            doc_length = len(tokens)

            for term, count in tf.items():
                self._index[term][doc_id] = count

            self._doc_info[doc_id] = {
                "length": doc_length,
                "title": title,
                "url": doc.get("url", ""),
                "source": doc.get("source", ""),
                "date": doc.get("date", ""),
                "tags": doc.get("tags", []),
                "category": doc.get("category", ""),
            }
            self._N += 1

        self._vocab = set(self._index.keys())

    def save(self, directory: str | Path) -> None:
        """Persist the index to *directory* (created if absent)."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        with open(path / self.INDEX_FILE, "wb") as fh:
            pickle.dump(
                {
                    "index": dict(self._index),
                    "doc_info": self._doc_info,
                    "N": self._N,
                },
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        meta = {
            "num_documents": self._N,
            "vocabulary_size": len(self._vocab),
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

        idx = cls()
        idx._index = defaultdict(dict, data["index"])
        idx._doc_info = data["doc_info"]
        idx._N = data["N"]
        idx._vocab = set(idx._index.keys())
        return idx

    def __repr__(self) -> str:
        return f"InvertedIndex(docs={self._N}, " f"vocab={len(self._vocab)})"

    def stats(self) -> dict:
        """Return a summary dict of index statistics."""
        return {
            "num_documents": self._N,
            "vocabulary_size": len(self._vocab),
        }


if __name__ == "__main__":
    from src.indexing.storage import DocumentStore
    import sys

    print(f"\n[Indexer] Building InvertedIndex...")

    store = DocumentStore("data")
    store.load_all()
    documents = store.all()

    if not documents:
        print("[Indexer] Error: No documents found in data/ directory.")
        sys.exit(1)

    print(f"[Indexer] Loaded {len(documents)} documents.")

    idx = InvertedIndex()
    idx.build(documents)

    idx.save("indexes/index")
    print(f"[Indexer] Indexing complete.\n")
