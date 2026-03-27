"""
Vector database module.

Provides:
    - BasicEmbeddings : LangChain-compatible embeddings using basic TF-IDF
    - VectorStore   : in-memory vector database with cosine-similarity search
"""

from .embeddings import BasicEmbeddings
from .vector_store import VectorStore

__all__ = ["BasicEmbeddings", "VectorStore"]
