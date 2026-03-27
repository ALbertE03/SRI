from __future__ import annotations

import pickle
from typing import Any

import numpy as np
from langchain_core.embeddings import Embeddings
from sklearn.feature_extraction.text import TfidfVectorizer

from src.indexing.indexer import InvertedIndex, TextNormalizer


class BasicEmbeddings(Embeddings):
    """
    LangChain embedding model using basic TF-IDF vectors.

    Parameters
    ----------
    normalizer : TextNormalizer | None
        Shared text normaliser.
    max_features : int
        Maximum vocabulary size.
    """

    def __init__(
        self,
        normalizer: TextNormalizer | None = None,
        max_features: int = 15_000,
    ) -> None:
        self.normalizer = normalizer or TextNormalizer()
        self.max_features = max_features

        self._vectorizer = TfidfVectorizer(
            tokenizer=self.normalizer.normalize,
            max_features=self.max_features,
            token_pattern=None,
            lowercase=False,
        )
        self._fitted = False

    def fit(self, documents: list[dict]) -> "BasicEmbeddings":
        """Fit the TF-IDF model from a list of document dicts."""
        if not documents:
            raise ValueError("Empty document list.")

        texts = []
        for doc in documents:
            text = f"{doc.get('title', '')} {doc.get('content', '')}"
            texts.append(text)

        self._vectorizer.fit(texts)
        self._fitted = True

        v = len(self._vectorizer.vocabulary_)
        print(f"[BasicEmbeddings] TF-IDF Fitted: {len(documents)} docs | {v} terms")
        return self

    def fit_from_index(self, index: "InvertedIndex") -> np.ndarray:
        """
        Build basic TF-IDF embeddings from the raw document texts.
        """
        doc_ids = list(index._doc_info.keys())
        doc_texts = []

        for doc_id in doc_ids:
            # Reconstruct bag of words as a string
            words = []
            for term, postings in index._index.items():
                if doc_id in postings:
                    words.extend([term] * postings[doc_id])
            doc_texts.append(" ".join(words))

        self._vectorizer.fit(doc_texts)
        self._fitted = True

        v = len(self._vectorizer.vocabulary_)
        print(
            f"[BasicEmbeddings] TF-IDF Reconstructed Fitted: {len(doc_ids)} docs | {v} terms"
        )

        return self._vectorizer.transform(doc_texts).toarray().astype(np.float32)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts into TF-IDF vectors."""
        if not self._fitted:
            raise RuntimeError("Not fitted.")

        matrix = self._vectorizer.transform(texts)
        # Convert sparse to dense list of lists
        return matrix.toarray().astype(np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query into a TF-IDF vector."""
        if not self._fitted:
            raise RuntimeError("Not fitted.")

        vector = self._vectorizer.transform([text])
        return vector.toarray().astype(np.float32).flatten().tolist()

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickling to handle the vectorizer cleanly."""
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Custom unpickling."""
        self.__dict__.update(state)

    def __repr__(self) -> str:
        vocab_size = (
            len(self._vectorizer.vocabulary_)
            if hasattr(self._vectorizer, "vocabulary_")
            else 0
        )
        return f"BasicEmbeddings(max_features={self.max_features}, vocab_size={vocab_size})"
