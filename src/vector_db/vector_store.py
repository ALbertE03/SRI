from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings
import numpy as np

if TYPE_CHECKING:
    from src.vector_db.embeddings import LSIEmbeddings


class VectorStore:
    """
    Vector database using Chroma DB for storage and retrieval.

    Parameters
    ----------
    embeddings : LSIEmbeddings | None
        An optional embedding model used for query transformation during search.
    """

    COLLECTION_NAME = "sri_documents"

    def __init__(self, embeddings: LSIEmbeddings | None = None) -> None:
        self._embeddings = embeddings

        # Connect to Chroma
        host = os.getenv("CHROMA_HOST")
        if host:
            # Docker / Remote mode
            port = int(os.getenv("CHROMA_PORT", 8000))
            print(f"[VectorStore] Connecting to Chroma at {host}:{port}...")
            self._client = chromadb.HttpClient(host=host, port=port)
        else:
            # Local mode
            persist_dir = str(Path("indexes/chroma").absolute())
            print(f"[VectorStore] Using local Chroma at {persist_dir}...")
            self._client = chromadb.PersistentClient(path=persist_dir)

        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    def setup(
        self, doc_ids: list[str], vectors: np.ndarray, doc_info: dict[str, dict]
    ) -> None:
        """
        Initialise the store with pre-computed vectors and metadata.
        """
        if len(doc_ids) != vectors.shape[0]:
            raise ValueError("Size mismatch between IDs and vectors.")

        # Chroma expects list of lists for embeddings
        embeddings_list = vectors.astype(float).tolist()

        # metadatas is a list of dicts corresponding to ids
        metadatas = [doc_info[did] for did in doc_ids]

        # Batch add/upsert
        print(f"[VectorStore] Upserting {len(doc_ids)} documents to Chroma...")
        self._collection.upsert(
            ids=doc_ids, embeddings=embeddings_list, metadatas=metadatas
        )
        print(f"[VectorStore] Initialised with {self._collection.count()} documents.")

    def search(
        self, query: str | list[float] | np.ndarray, top_k: int = 10
    ) -> list[dict]:
        """
        Rank documents by similarity using Chroma.
        """
        # Convert query to vector if it's a string
        if isinstance(query, str):
            if self._embeddings is None:
                raise RuntimeError("Need embeddings model to search raw strings.")
            q_vec = self._embeddings.embed_query(query)
        else:
            q_vec = list(query) if isinstance(query, np.ndarray) else query

        # Query Chroma
        results = self._collection.query(
            query_embeddings=[q_vec],
            n_results=top_k,
            include=["metadatas", "distances"],
        )

        # Format output to match previous interface
        output = []
        if not results["ids"]:
            return output

        for i, (doc_id, metadata, distance) in enumerate(
            zip(results["ids"][0], results["metadatas"][0], results["distances"][0]),
            start=1,
        ):

            # So score = 1 - distance
            score = 1.0 - float(distance)

            output.append(
                {
                    "rank": i,
                    "doc_id": doc_id,
                    "score": round(score, 6),
                    "title": metadata.get("title", ""),
                    "url": metadata.get("url", doc_id),
                    "source": metadata.get("source", ""),
                    "date": metadata.get("date", ""),
                    "tags": metadata.get("tags", []),
                    "category": metadata.get("category", ""),
                }
            )

        return output

    def add_document(self, document: dict) -> None:
        """
        Add a single document. Requires self._embeddings.
        """
        if self._embeddings is None:
            raise RuntimeError("Need embeddings model to add documents.")

        doc_id = str(document.get("id") or document.get("url", ""))
        text = f"{document.get('title', '')} {document.get('content', '')}"
        vec = self._embeddings.embed_query(text)

        # Clean metadata for Chroma (must be str, int, float, or bool)
        metadata = {
            k: v
            for k, v in document.items()
            if k not in ("id", "content") and isinstance(v, (str, int, float, bool))
        }

        self._collection.upsert(ids=[doc_id], embeddings=[vec], metadatas=[metadata])

    def save(self, directory: str | Path) -> None:
        """In-process persistence is handled by PersistentClient."""
        print(
            f"[VectorStore] Data persistent in Chroma collection '{self.COLLECTION_NAME}'"
        )

    @classmethod
    def load(
        cls, directory: str | Path, embeddings: LSIEmbeddings | None = None
    ) -> "VectorStore":
        """Load the store."""
        # Note: directory argument is ignored if using local persistent path in __init__
        return cls(embeddings=embeddings)

    def stats(self) -> dict:
        return {
            "num_documents": self._collection.count(),
            "collection_name": self.COLLECTION_NAME,
        }

    def __repr__(self) -> str:
        return f"VectorStore(Chroma: {self.COLLECTION_NAME}, docs={self._collection.count()})"
