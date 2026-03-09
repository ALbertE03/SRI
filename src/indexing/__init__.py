"""
Indexing module

Provides:
    - InvertedIndex   : builds, queries and persists an inverted index
    - DocumentStore   : JSON-backed document store used by the index
    - TextNormalizer  : tokenisation / stemming / stop-word removal
"""

from .indexer import InvertedIndex, TextNormalizer
from .storage import DocumentStore

__all__ = ["InvertedIndex", "TextNormalizer", "DocumentStore"]
