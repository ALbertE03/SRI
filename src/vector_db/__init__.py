"""
Vector database module.

Provides:
    - LSIEmbeddings : LangChain-compatible embeddings using the LSI pipeline
    - VectorStore   : in-memory vector database with cosine-similarity search
"""

from .embeddings import LSIEmbeddings
from .vector_store import VectorStore

__all__ = ["LSIEmbeddings", "VectorStore"]
