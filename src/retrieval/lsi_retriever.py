from __future__ import annotations

import math
import pickle
from pathlib import Path

import numpy as np

from src.indexing.indexer import InvertedIndex, TextNormalizer
from src.vector_db.embeddings import LSIEmbeddings
from src.vector_db.vector_store import VectorStore


class LSIRetriever:
    """
    High-level retriever using Latent Semantic Indexing.

    Coordinates the embedding model and the vector storage to provide
    a unified retrieval interface.

    Parameters
    ----------
    vector_store : VectorStore | None
        The underlying storage for document embeddings.
    embeddings : LSIEmbeddings | None
        The model responsible for text-to-vector transformation.
    normalizer : TextNormalizer | None
        Shared text normaliser.
    """

    MODEL_FILE = "lsi_model.pkl"

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embeddings: LSIEmbeddings | None = None,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.normalizer = normalizer or TextNormalizer()

    @classmethod
    def from_inverted_index(
        cls,
        index: "InvertedIndex",
        n_components: int = 200,
    ) -> "LSIRetriever":
        """
        Build a complete LSI retrieval system from an InvertedIndex.

        This is the primary way to initialize the retriever, as it reuses
        the term frequencies already computed by the indexer.
        """
        #  Fit the LSI model (Term-Document Matrix with Log-TF weighting)
        print(f"[LSIRetriever] Fitting LSI model with {n_components} components...")
        embeddings = LSIEmbeddings(
            n_components=n_components, normalizer=index.normalizer
        )
        doc_vectors = embeddings.fit_from_index(index)

        #  Initialize and setup the VectorStore
        vs = VectorStore(embeddings=embeddings)
        vs.setup(list(index._doc_info.keys()), doc_vectors, index._doc_info)

        return cls(vector_store=vs, embeddings=embeddings, normalizer=index.normalizer)

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        category_filter: str | None = None,
    ) -> list[dict]:
        """
        Search for relevant documents in the LSI latent space.
        """
        if self.vector_store is None:
            raise RuntimeError(
                "LSIRetriever not initialised. Call from_inverted_index() first."
            )

        results = self.vector_store.search(query, top_k=top_k * 5)

        if category_filter:
            results = [r for r in results if r.get("category") == category_filter]

        return results[:top_k]

    def save(self, directory: str | Path) -> None:
        """Persist the retriever state and its components."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        # Save VectorStore (tells Chroma to ensure persistence)
        if self.vector_store:
            self.vector_store.save(directory)

        # Save LSI model and retriever specific state
        state = {
            "embeddings": self.embeddings,
            "normalizer": self.normalizer,
        }
        with open(path / self.MODEL_FILE, "wb") as fh:
            pickle.dump(state, fh)

        print(f"[LSIRetriever] Saved to {directory}")

    @classmethod
    def load(cls, directory: str | Path) -> "LSIRetriever":
        """Load a persisted retriever from a directory."""
        path = Path(directory)
        model_path = path / cls.MODEL_FILE

        if not model_path.exists():
            # Fallback
            vs = VectorStore()
            return cls(vector_store=vs)

        #  Load embeddings and normalizer
        with open(model_path, "rb") as fh:
            state = pickle.load(fh)

        embeddings = state.get("embeddings")
        normalizer = state.get("normalizer")

        # Load VectorStore with the embeddings
        vs = VectorStore.load(directory, embeddings=embeddings)

        return cls(
            vector_store=vs,
            embeddings=embeddings,
            normalizer=normalizer,
        )

    def stats(self) -> dict:
        """Return combined statistics of the system."""
        if self.vector_store:
            return self.vector_store.stats()
        return {}

    def __repr__(self) -> str:
        return f"LSIRetriever(vector_store={self.vector_store})"
