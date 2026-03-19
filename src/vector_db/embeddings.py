from __future__ import annotations

import math
from collections import Counter

import numpy as np
from langchain_core.embeddings import Embeddings
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from src.indexing.indexer import TextNormalizer


class LSIEmbeddings(Embeddings):
    """
    LangChain embedding model using LSI.

    Parameters
    ----------
    n_components : int
        Dimensionality of the output latent space.
    normalizer : TextNormalizer | None
        Shared text normaliser.
    max_features : int
        Maximum vocabulary size.
    """

    def __init__(
        self,
        n_components: int = 200,
        normalizer: TextNormalizer | None = None,
        max_features: int = 15_000,
    ) -> None:
        self.n_components = n_components
        self.normalizer = normalizer or TextNormalizer()
        self.max_features = max_features

        # Fitted state
        self._svd: TruncatedSVD | None = None
        self._vocab: dict[str, int] = {}  # term -> column index
        self._fitted = False

    def fit(self, documents: list[dict]) -> "LSIEmbeddings":
        """Fit the LSI model from a list of document dicts."""
        if not documents:
            raise ValueError("Empty document list.")

        # Collect tokens and build vocabulary by frequency
        token_lists = []
        df_counts: dict[str, int] = {}
        for doc in documents:
            text = f"{doc.get('title', '')} {doc.get('content', '')}"
            tokens = self.normalizer.normalize(text)
            token_lists.append(tokens)
            for t in set(tokens):
                df_counts[t] = df_counts.get(t, 0) + 1

        sorted_terms = sorted(
            df_counts.keys(), key=lambda t: df_counts[t], reverse=True
        )
        vocab_terms = sorted_terms[: self.max_features]
        self._vocab = {term: i for i, term in enumerate(vocab_terms)}
        V = len(self._vocab)
        N = len(token_lists)

        # 2. Build Term-Document Matrix with Log-TF weighting
        # A[i, j] = log(1 + tf_ij)
        matrix = np.zeros((N, V), dtype=np.float32)
        for row, tokens in enumerate(token_lists):
            counts = Counter(tokens)
            for term, count in counts.items():
                col = self._vocab.get(term)
                if col is not None:
                    matrix[row, col] = math.log1p(count)

        # 3. Apply SVD
        self._fit_svd(matrix)
        return self

    def fit_from_index(self, index: "InvertedIndex") -> np.ndarray:
        """
        Fits LSI from an InvertedIndex and returns document vectors.
        Supported by Deerwester et al. (1990) using log-weighting.
        """
        # Build vocabulary sorted by document frequency (highest first)
        df_counts = {term: len(postings) for term, postings in index._index.items()}
        sorted_terms = sorted(
            df_counts.keys(), key=lambda t: df_counts[t], reverse=True
        )
        vocab_terms = sorted_terms[: self.max_features]
        self._vocab = {term: i for i, term in enumerate(vocab_terms)}

        V = len(self._vocab)
        N = len(index._doc_info)
        doc_ids = list(index._doc_info.keys())
        doc_id_to_row = {doc_id: i for i, doc_id in enumerate(doc_ids)}

        # Build log-TF matrix
        matrix = np.zeros((N, V), dtype=np.float32)
        for term, postings in index._index.items():
            col = self._vocab.get(term)
            if col is None:
                continue
            for doc_id, count in postings.items():
                row = doc_id_to_row.get(doc_id)
                if row is not None:
                    matrix[row, col] = math.log1p(count)

        self._fit_svd(matrix)

        return self.transform_matrix(matrix)

    def _fit_svd(self, matrix: np.ndarray) -> None:
        """Helper to fit SVD on a weighted term-document matrix."""
        N, V = matrix.shape
        k = min(self.n_components, N - 1, V - 1)
        if k < 1:
            raise ValueError(f"Too few docs ({N}) or terms ({V}) for LSI.")

        # L2-normalize documents before SVD (optional but common for better results)
        matrix = normalize(matrix, norm="l2")

        self._svd = TruncatedSVD(
            n_components=k,
            algorithm="randomized",
            n_iter=7,
            random_state=42,
        )
        self._svd.fit(matrix)
        self._fitted = True

        ev = self._svd.explained_variance_ratio_.sum()
        print(
            f"[LSIEmbeddings] Classic LSI Fitted: {N} docs | {V} terms | "
            f"{k} dims | explained variance: {ev:.3f}"
        )

    def transform_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """
        Project a pre-built Log-TF matrix into the latent space.

        Following Barbara Rosario (2000): q_hat = q^T * T * S^-1
        """
        if not self._fitted or self._svd is None:
            raise RuntimeError("Not fitted.")

        #  Normalise input rows (documents)
        matrix = normalize(matrix, norm="l2")

        # Project to latent space: raw_latent = matrix * V
        # self._svd.transform(matrix) returns matrix * V
        latent = self._svd.transform(matrix)

        # Scale by inverse of singular values (S^-1)
        # This is the "folding-in" step described in the paper.
        latent = latent / self._svd.singular_values_

        # Final L2-normalisation of the reduced vectors
        return normalize(latent, norm="l2").astype(np.float32)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts."""
        vectors = []
        for text in texts:
            vectors.append(self.embed_query(text))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a single text using the LSI projection.
        Formula: q_hat = q^T * T * S^-1
        """
        if not self._fitted or self._svd is None:
            raise RuntimeError("Not fitted.")

        tokens = self.normalizer.normalize(text)
        V = len(self._vocab)
        if not tokens:
            return [0.0] * self._svd.n_components

        # Create log-TF vector (q)
        counts = Counter(tokens)
        vec = np.zeros(V, dtype=np.float32)
        for term, count in counts.items():
            if term in self._vocab:
                vec[self._vocab[term]] = math.log1p(count)

        # 2. L2-normalize query term vector
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm

        # Project: q * T
        # svd.transform returns X * V
        q_latent = self._svd.transform(vec.reshape(1, -1))

        #  Scale by S^-1 (Singular Value scaling from paper)
        q_latent = q_latent / self._svd.singular_values_

        #  Final L2-normalization for cosine similarity
        q_norm = float(np.linalg.norm(q_latent))
        if q_norm > 0:
            q_latent /= q_norm

        return q_latent.flatten().tolist()

    def __repr__(self) -> str:
        k = self._svd.n_components if self._svd else 0
        return f"LSIEmbeddings(dims={k}, vocab={len(self._vocab)}, classic=True)"
