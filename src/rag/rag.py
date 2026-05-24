from __future__ import annotations

from typing import Any, List, Dict, Optional
from src.generator.answer_generator import AnswerGenerator
from src.indexing.chunker import DocumentChunker
from src.positioning.ranker import ResultRanker
from src.utils.logger import rag_logger as logger
from src.config import (
    RAG_COOCCURRENCE_WINDOW,
    RAG_ENABLE_QUERY_EXPANSION,
    RAG_LM_RETRIEVER_WEIGHT,
    RAG_QUERY_EXPANSION_TERMS,
    RAG_RELEVANCE_THRESHOLD,
    RAG_RETRIEVER_K,
    RAG_VECTOR_RETRIEVER_WEIGHT
)
from src.errors.internet_search_error import WebSearchExecutionError
from src.errors.rag_errors import (
    RAGPipelineInitializationError,
    RAGRetrievalError,
)
from src.errors.retrieval_errors import QueryProcessingError
from src.retrieval.lm_retriever import LMRetriever
from src.retrieval.query_processor import QueryProcessor
from src.retrieval.langchain_retriever import LangChainLMRetriever
from src.vector_db.vector_store import VectorStore
from src.vector_db.langchain_retriever import LangChainVectorRetriever
from src.search_internet.searcher import WebSearcher
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
import numpy as np
class EnsembleRetriever(BaseRetriever):
    """Simple ensemble retriever combining LM and vector retrievers."""
    retrievers: List[Any]
    weights: List[float]
    k:int=60

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Any]:
        """Combine results from multiple retrievers with weighted scoring."""
        all_docs = {}  # {content_hash: (doc, weighted_score)}
        
        for retriever, weight in zip(self.retrievers, self.weights):
            try:
                docs = retriever.invoke(query)
                for i, doc in enumerate(docs,start=1):
                    score = weight/(self.k+i) # Rank-WRRF
                    doc_hash = hash(doc.page_content)
                    
                    if doc_hash in all_docs:
                        all_docs[doc_hash] = (doc, all_docs[doc_hash][1] + score)
                    else:
                        all_docs[doc_hash] = (doc, score)
            except Exception:
                pass
        
        sorted_docs = sorted(all_docs.values(), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in sorted_docs]


class RAGPipeline:
    """
    Complete RAG pipeline using LangChain LCEL.
    """

    def __init__(
        self,
        retriever_lm: LMRetriever,
        vector_store: VectorStore,
        web_searcher: Optional[WebSearcher],
        query_processor: Optional[QueryProcessor],
        ranker: Optional[ResultRanker] = None,

        relevance_threshold: float | None = None,
        enable_query_expansion: bool | None = None,
        expansion_terms: int | None = None,
        cooccurrence_window: int | None = None,
    ) -> None:
        """Initialize RAG pipeline with dependency injection."""
        try:
            self.vector_store = vector_store
            
            # Dependency injection
            self.web_searcher = web_searcher 
            self.query_processor = query_processor 
            self.rank = ranker
            
            self.relevance_threshold = (
                relevance_threshold
                if relevance_threshold is not None
                else RAG_RELEVANCE_THRESHOLD
            )
            self.enable_query_expansion = (
                enable_query_expansion
                if enable_query_expansion is not None
                else RAG_ENABLE_QUERY_EXPANSION
            )
            self.expansion_terms = (
                expansion_terms
                if expansion_terms is not None
                else RAG_QUERY_EXPANSION_TERMS
            )
            self.cooccurrence_window = (
                cooccurrence_window
                if cooccurrence_window is not None
                else RAG_COOCCURRENCE_WINDOW
            )
            
            self.raw_lm_retriever = retriever_lm
            if self.enable_query_expansion:
                cooccurrence_stats = self.query_processor.precompute_cooccurrence_matrix(
                    self.raw_lm_retriever.index,
                    self.cooccurrence_window,
                )
                logger.info(
                    "Co-occurrence matrix ready at startup: "
                    f"{cooccurrence_stats['terms']} terms, "
                    f"{cooccurrence_stats['pairs']} pairs, "
                    f"window={cooccurrence_stats['window']}"
                )

            #  Initialize Retrievers
            self.lm_retriever = LangChainLMRetriever(
                retriever=retriever_lm, k=RAG_RETRIEVER_K
            )
            self.vector_retriever = LangChainVectorRetriever(
                vectorstore=vector_store._vectorstore, k=RAG_RETRIEVER_K
            )

            # Create Ensemble Retriever (Hybrid Search)
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[self.lm_retriever, self.vector_retriever],
                weights=[RAG_LM_RETRIEVER_WEIGHT, RAG_VECTOR_RETRIEVER_WEIGHT],
            )
    

        except Exception as exc:
            raise RAGPipelineInitializationError(
                "Failed to initialize RAG pipeline."
            ) from exc

    async def retrieve(
            self,
            query: str,
            chunker: Optional[DocumentChunker] = None,
            top_k: int | None = None,
            use_expand: bool = True,
            relevance_threshold: float | None = None,
            max_doc_chars: int | None = None,
            use_internet_search: bool = True,
        ) -> Dict[str, Any]:
            """
            Retrieve documents using the RAG pipeline.
            
            - returns context and documents for external generation.
            
            Parameters
            ----------
            query : str
                User query in Spanish
            top_k : int, optional
                Number of documents to retrieve
            use_expand : bool
                Whether to apply co-occurrence query expansion
            relevance_threshold : float, optional
                RAG relevance threshold for web search fallback
            max_doc_chars : int, optional
                Max characters per document
            use_internet_search : bool
                Whether to allow internet fallback search
                
            Returns
            -------
            dict
                Contains: query, context, documents, sources, search_performed, top_local_score
            """
            effective_threshold = (
                relevance_threshold if relevance_threshold is not None 
                else RAG_RELEVANCE_THRESHOLD
            )
            effective_top_k = top_k if top_k is not None else RAG_RETRIEVER_K
          
            logger.info(f"RAG: Processing query: {query}")

            # Process query: normalize, extract filters, optional expansion
            try:
                processed_query = self.query_processor.process(query)
                logger.info(f"Normalized query: {processed_query.text}")
            except QueryProcessingError as exc:
                raise RAGRetrievalError(f"Query processing failed: {exc}") from exc

            # Get initial query weights from processed query
            q_weights = processed_query.to_weights()
            retrieval_query_text = processed_query.text
            expansion_status: list[str] = []

            # Apply co-occurrence query expansion if enabled
            if self.enable_query_expansion and use_expand:
                logger.info("Applying co-occurrence query expansion...")
                
                try:
                    q_weights_expanded = self.query_processor.apply_cooccurrence_expansion(
                        q_weights,
                        processed_query.text,
                        expansion_terms=self.expansion_terms,
                        window_size=self.cooccurrence_window,
                        index=self.raw_lm_retriever.index,
                    )
                    q_weights = q_weights_expanded
                    retrieval_query_text = self.query_processor.weights_to_query_text(
                        q_weights,
                        processed_query.text,
                    )
                    processed_query.expanded = True
                    added_terms = [
                        term for term in q_weights if term not in processed_query.tokens
                    ]
                    if added_terms:
                        expansion_status.append(
                            "Expanded query terms: " + ", ".join(added_terms[: self.expansion_terms])
                        )
                    logger.info("Query expanded via co-occurrence matrix")
                    retrieval_query_text =retrieval_query_text
                    logger.info(f"Expanded query: {retrieval_query_text}")
                except Exception as exc:
                    logger.info(f"Co-occurrence expansion skipped: {exc}")


            try:
                if hasattr(self.lm_retriever, 'k'):
                    self.lm_retriever.k = effective_top_k
                if hasattr(self.vector_retriever, 'k'):
                    self.vector_retriever.k = effective_top_k

                local_docs = self.ensemble_retriever.invoke(retrieval_query_text)
                logger.info(f"Retrieved {len(local_docs)} docs from ensemble")
                
            except Exception as exc:
                raise RAGRetrievalError("Failed to retrieve local documents.") from exc

    
            top_score = 0.0
            for doc in local_docs:
                score = doc.metadata.get("score", 0)
                if isinstance(score, float):
                    top_score = max(top_score, score)

            internet_docs_chunked = []
            logger.info(f"top local score: {top_score}")
            if use_internet_search and top_score < effective_threshold:
                logger.info(
                    f"Local relevance ({top_score:.2f}) below threshold ({effective_threshold}). Searching internet..."
                )
                
                try:
                    internet_docs = self.web_searcher.search(processed_query.text)
                    if chunker and internet_docs:
                  
                        docs_as_dicts = [
                            {
                                "id": doc.metadata.get("url", f"web_{i}"),
                                "content": doc.page_content,
                                "title": doc.metadata.get("title", "Internet Result"),
                                "url": doc.metadata.get("url", ""),
                                "source": doc.metadata.get("source", "Internet"),
                            }
                            for i, doc in enumerate(internet_docs)
                        ]
                        chunks_as_dicts = chunker.chunk_corpus(docs_as_dicts)
                        internet_docs_chunked=[]
                        for c in chunks_as_dicts:
                            if not c.get("content"):
                                continue
                                
                            relevance_score = self._calculate_relevance_score(
                                processed_query.text, 
                                c["content"]
                            )
                            
                            doc = LCDocument(
                                page_content=c["content"],
                                metadata={
                                    "title": c.get("title", "Internet Result"),
                                    "url": c.get("url", ""),
                                    "source": c.get("source", "Internet"),
                                    "chunk_id": c.get("chunk_id", ""),
                                    "chunk_index": c.get("chunk_index", 0),
                                    "score": relevance_score,  
                                    "retriever": "web_search"
                                },
                            )
                            internet_docs_chunked.append(doc)
                    else:
                        internet_docs_chunked = internet_docs
                except WebSearchExecutionError as exc:
                    logger.info(f"Internet search failed: {exc}")
                    internet_docs_chunked = []

            # Combine local and internet documents
            all_docs = local_docs + internet_docs_chunked
            
            logger.info(f"Ranking {len(all_docs)} documents...")
            ranked_docs = self.rank.rank(all_docs)

            # Get top K from ranked results
            docs = ranked_docs[:effective_top_k]
            

            logger.info(f"Using top {len(docs)} ranked documents")

            if internet_docs_chunked:
                logger.info(f"save {len(internet_docs_chunked)} web docs in ChromaDB")
                await self.vector_store.add_documents(internet_docs_chunked)

            logger.info(f"Retrieved {len(docs)} documents for context")
   
            return {
                "query": query,
                "documents": docs, 
                "expanded_query":retrieval_query_text,
                "top_local_score": top_score
            }

    def __str__(self):
        return f"RAGPipeline()"
    
    def _calculate_relevance_score(self, query: str, document_content: str) -> float:

        query_emb = self.vector_store._embeddings.embed_query(query)
        doc_emb = self.vector_store._embeddings.embed_query(document_content)
        query_norm = np.linalg.norm(query_emb)
        doc_norm = np.linalg.norm(doc_emb)
            
        if query_norm == 0 or doc_norm == 0:
                return 0.0
                
        cosine_sim = np.dot(query_emb, doc_emb) / (query_norm * doc_norm)
        return float((cosine_sim + 1) / 2)