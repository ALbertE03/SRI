"""
Retrieval module.

Provides:
    - LSIRetriever   : Latent Semantic Indexing retriever (Deerwester et al., 1990)
    - QueryProcessor : query expansion, normalisation and result re-ranking
"""

from .lsi_retriever  import LSIRetriever
from .query_processor import QueryProcessor

__all__ = ["LSIRetriever", "QueryProcessor"]
