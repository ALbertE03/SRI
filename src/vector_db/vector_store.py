from __future__ import annotations

import json
from typing import Any
import numpy as np
from tqdm import tqdm

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from src.config import VECTOR_DB_COLLECTION_NAME, VECTOR_DB_PERSIST_DIR, VECTOR_DB_TOP_K
from src.errors.vector_db_errors import VectorStoreOperationError
from src.utils.logger import vector_logger as logger

class VectorStore:
    """
    Vector database using Chroma DB via LangChain.
    """

    COLLECTION_NAME = VECTOR_DB_COLLECTION_NAME

    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings
        self._persist_dir = VECTOR_DB_PERSIST_DIR

        self._vectorstore = Chroma(
            collection_name=self.COLLECTION_NAME,
            embedding_function=self._embeddings,
            persist_directory=self._persist_dir,
            collection_metadata={"hnsw:space": "cosine"},
        )
    
    def __str__(self):
        return f"VectorStore (Chroma LC: {self.COLLECTION_NAME})"
    
    def setup(
            self,
            doc_ids: list[str],
            texts: list[str],
            metadata: list[str] = None,
            reset: bool = False,
            batch_size: int = 5000,
        ) -> None:
            """
            Initialise the store with documents. Uses batching with tqdm.
            """
            try:
                if reset:
                    self._vectorstore.delete_collection()
                    self._vectorstore = Chroma(
                        collection_name=self.COLLECTION_NAME,
                        embedding_function=self._embeddings,
                        persist_directory=self._persist_dir,
                        collection_metadata={"hnsw:space": "cosine"},
                    )

                logger.info(f"Adding {len(doc_ids)} documents to Chroma in batches...")

                if metadata is None:
                    metadata = [{} for _ in range(len(doc_ids))]
                
                total = len(doc_ids)
                num_batches = int(np.ceil(total / batch_size))
                
                
                pbar = tqdm(total=num_batches, desc="Adding batches to Chroma", unit="batch")
                
                for batch_idx in range(num_batches):
                    start = batch_idx * batch_size
                    end = min(start + batch_size, total)
                    
                    batch_ids = doc_ids[start:end]
                    batch_texts = texts[start:end]
                    metadata_batch = metadata[start:end]
                    
                    self._vectorstore.add_texts(
                        texts=batch_texts,
                        ids=batch_ids,
                        metadatas=metadata_batch
                    )
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        "docs": f"{end}/{total}",
                        "batch": f"{batch_idx + 1}/{num_batches}"
                    })

                pbar.close()
                logger.info(f"Successfully added {total} documents in {num_batches} batches")

            except Exception as exc:
                raise VectorStoreOperationError("Failed to setup vector store.") from exc

    async def add_documents(self, documents: list[Any], batch_size: int = 5000) -> None:
        """
        Add LangChain Document objects to the store. Uses numpy batching + tqdm.
        """
        try:
            total = len(documents)
            num_batches = int(np.ceil(total / batch_size))
            
            logger.info(f"Adding {total} documents to Chroma in {num_batches} batches...")

            pbar = tqdm(total=num_batches, desc="Adding batches to Chroma", unit="batch")
            
            for batch_idx in range(num_batches):
                start = batch_idx * batch_size
                end = min(start + batch_size, total)
                batch = documents[start:end]
                
                if batch_idx > 0 and batch_idx % max(1, num_batches // 10) == 0:
                    logger.info(f"Progress: {end}/{total} documents ({end/total*100:.1f}%)")
                
                self._vectorstore.add_documents(batch)
                pbar.update(1)
                pbar.set_postfix({
                    "docs": f"{end}/{total}",
                    "batch": f"{batch_idx + 1}/{num_batches}"
                })

            pbar.close()
            
            logger.info(f"Total documents in store: {self.stats()['num_documents']}")
        except Exception as exc:
            raise VectorStoreOperationError("Failed to add documents.") from exc

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """
        Rank documents by similarity.
        """
        if top_k is None:
            top_k = VECTOR_DB_TOP_K
        try:
            results = self._vectorstore.similarity_search_with_relevance_scores(
                query,
                k=top_k,
            )

            output = []
            for i, (doc, score) in enumerate(results, start=1):
                metadata = doc.metadata
                output.append(
                    {
                        "rank": i,
                        "doc_id": doc.id
                        if hasattr(doc, "id")
                        else metadata.get("url", ""),
                        "score": round(score, 6),
                        "title": metadata.get("title", ""),
                        "url": metadata.get("url", ""),
                        "source": metadata.get("source", ""),
                        "content": doc.page_content,
                        "content_preview": doc.page_content[:200] + "...",
                        "metadata": metadata,
                    }
                )

            return output
        except Exception as exc:
            raise VectorStoreOperationError("Vector search failed.") from exc

    def as_retriever(self, **kwargs):
        """Return the LangChain retriever interface."""
        return self._vectorstore.as_retriever(**kwargs)

    def stats(self) -> dict:
        try:
            count = self._vectorstore._collection.count()
            return {
                "num_documents": count,
                "collection_name": self.COLLECTION_NAME,
            }
        except Exception as exc:
            raise VectorStoreOperationError("Failed to read vector store stats.") from exc

    def __repr__(self) -> str:
        return f"VectorStore(Chroma LC: {self.COLLECTION_NAME})"
    
    def __str__(self) -> str:
        return f"VectorStore(Chroma LC: {self.COLLECTION_NAME})"