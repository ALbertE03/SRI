"""
In-memory vector store for document embeddings.

This module provides a pure storage and search layer. It does not
know how to generate embeddings; it simply stores vectors and
performs cosine-similarity search.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

from src.vector_db.embeddings import LSIEmbeddings


class VectorStore:
    """
    In-memory vector database for dense embeddings.

    Parameters
    ----------
    embeddings : LSIEmbeddings | None
        An optional embedding model used for query transformation
        during search and for incremental document addition.
    """

    STORE_FILE = "vector_store.pkl"
    META_FILE = "vector_store_meta.json"

    def __init__(self, embeddings: LSIEmbeddings | None = None) -> None:
        self._embeddings = embeddings

        # Internal state
        self._doc_vectors: np.ndarray | None = None  # (N, D) L2-normalised
        self._doc_ids: list[str] = []
        self._doc_info: dict[str, dict] = {}
        self._N: int = 0
        self._dims: int = 0

    def setup(
        self, doc_ids: list[str], vectors: np.ndarray, doc_info: dict[str, dict]
    ) -> None:
        """
        Initialise the store with pre-computed vectors and metadata.

        Parameters
        ----------
        doc_ids : List of document IDs.
        vectors : NumPy matrix (N, D) of document vectors.
        doc_info : Dictionary mapping doc_id to its metadata.
        """
        if len(doc_ids) != vectors.shape[0]:
            raise ValueError("Size mismatch between IDs and vectors.")

        self._doc_ids = list(doc_ids)
        self._doc_vectors = vectors.astype(np.float32)
        self._doc_info = dict(doc_info)
        self._N = len(self._doc_ids)
        self._dims = self._doc_vectors.shape[1]

        print(
            f"[VectorStore] Initialised: {self._N} documents | "
            f"{self._dims} dimensions"
        )

    def search(
        self, query: str | list[float] | np.ndarray, top_k: int = 10
    ) -> list[dict]:
        """
        Rank documents by cosine similarity.

        Parameters
        ----------
        query : Either a raw string (needs self._embeddings), or a pre-computed vector.
        top_k : Number of results to return.

        Returns
        -------
        List of result dicts with doc_id, score, and metadata.
        """
        if self._doc_vectors is None:
            raise RuntimeError("VectorStore is empty. Call setup() first.")

        # Convert query to vector if it's a string
        if isinstance(query, str):
            if self._embeddings is None:
                raise RuntimeError(
                    "Cannot search string query without embeddings model."
                )
            q_vec = np.array(self._embeddings.embed_query(query), dtype=np.float32)
        else:
            q_vec = np.array(query, dtype=np.float32)

        q_vec = q_vec.reshape(1, -1)

        # Ensure query is L2-normalised (doc vectors should already be)
        q_norm = float(np.linalg.norm(q_vec))
        if q_norm > 0:
            q_vec /= q_norm

        # Cosine similarity
        similarities = (self._doc_vectors @ q_vec.T).flatten()

        # Rank descending
        ranked_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(ranked_indices, start=1):
            doc_id = self._doc_ids[int(idx)]
            info = self._doc_info.get(doc_id, {})
            results.append(
                {
                    "rank": rank,
                    "doc_id": doc_id,
                    "score": round(float(similarities[int(idx)]), 6),
                    "title": info.get("title", ""),
                    "url": info.get("url", doc_id),
                    "source": info.get("source", ""),
                    "date": info.get("date", ""),
                    "tags": info.get("tags", []),
                    "category": info.get("category", ""),
                }
            )

        return results

    def add_document(self, document: dict) -> None:
        """
        Add a single document. Requires self._embeddings.
        """
        if self._embeddings is None:
            raise RuntimeError("Need embeddings model to add raw documents.")
        if self._doc_vectors is None:
            raise RuntimeError("Initialise with setup() first.")

        doc_id = str(document.get("id") or document.get("url", ""))
        text = f"{document.get('title', '')} {document.get('content', '')}"

        vec = np.array(self._embeddings.embed_query(text), dtype=np.float32).reshape(
            1, -1
        )

        self._doc_vectors = np.vstack([self._doc_vectors, vec])
        self._doc_ids.append(doc_id)
        self._doc_info[doc_id] = {
            "title": document.get("title", ""),
            "url": document.get("url", ""),
            "source": document.get("source", ""),
            "date": document.get("date", ""),
            "tags": document.get("tags", []),
            "category": document.get("category", ""),
        }
        self._N += 1

    def save(self, directory: str | Path) -> None:
        """Persist the vector store to *directory*."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        with open(path / self.STORE_FILE, "wb") as fh:
            pickle.dump(
                {
                    "embeddings": self._embeddings,
                    "doc_vectors": self._doc_vectors,
                    "doc_ids": self._doc_ids,
                    "doc_info": self._doc_info,
                    "N": self._N,
                    "dims": self._dims,
                },
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        meta = {
            "num_documents": self._N,
            "embedding_dimensions": self._dims,
        }
        with open(path / self.META_FILE, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2, ensure_ascii=False)

        print(f"[VectorStore] Saved to {path / self.STORE_FILE}")

    @classmethod
    def load(cls, directory: str | Path) -> "VectorStore":
        """Load a previously saved vector store from *directory*."""
        path = Path(directory)
        store_path = path / cls.STORE_FILE
        if not store_path.exists():
            raise FileNotFoundError(f"Vector store not found at {store_path}.")

        with open(store_path, "rb") as fh:
            data = pickle.load(fh)

        obj = cls(embeddings=data["embeddings"])
        obj._doc_vectors = data["doc_vectors"]
        obj._doc_ids = data["doc_ids"]
        obj._doc_info = data["doc_info"]
        obj._N = data["N"]
        obj._dims = data["dims"]
        return obj

    def __repr__(self) -> str:
        return f"VectorStore(docs={self._N}, dims={self._dims})"

    def stats(self) -> dict:
        return {
            "num_documents": self._N,
            "embedding_dimensions": self._dims,
        }
