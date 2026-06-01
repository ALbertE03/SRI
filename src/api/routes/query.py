
import logging
from fastapi import APIRouter, HTTPException
logger = logging.getLogger(__name__)
from typing import Dict, Any, Iterable
from src.api.models import QueryRequest, QueryResponse,ErrorResponse,FeedbackRequest,FeedbackResponse
from src.errors.rag_errors import (
    RAGError,
    RAGPipelineInitializationError,
    RAGRetrievalError,
    RAGAnswerGenerationError,
)
from src.errors.internet_search_error import WebSearchExecutionError



_session_store: Dict[str, Dict[str, Any]] = {}
router = APIRouter(prefix="/query", tags=["Query"])
globals = {}

def set_dependencies(globals_dict):
    """Set dependencies from the main server."""
    globals.update(globals_dict)


def _metadata_for(doc: Any) -> Dict[str, Any]:
    if hasattr(doc, "metadata"):
        return dict(getattr(doc, "metadata") or {})
    if isinstance(doc, dict):
        return dict(doc.get("metadata") or {})
    return {}


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _document_text(doc: Any, metadata: Dict[str, Any]) -> str:
    if metadata.get("front_prev"):
        return str(metadata["front_prev"])
    if hasattr(doc, "page_content"):
        return getattr(doc, "page_content") or ""
    if isinstance(doc, dict):
        return _first_non_empty(
            doc.get("content"),
            doc.get("text"),
            doc.get("page_content"),
            doc.get("content_preview"),
            metadata.get("front_prev"),
        )
    return str(doc) if doc is not None else ""


def _document_aliases(serialized: Dict[str, Any]) -> Iterable[str]:
    metadata = serialized.get("metadata") or {}
    aliases = {
        serialized.get("id"),
        serialized.get("doc_id"),
        serialized.get("chunk_id"),
        serialized.get("document_key"),
        serialized.get("url"),
        metadata.get("doc_id"),
        metadata.get("chunk_id"),
        metadata.get("url"),
        metadata.get("source"),
    }
    return [str(alias) for alias in aliases if alias]


def _serialize_document(doc: Any, fallback_idx: int = 0) -> Dict[str, Any]:
    metadata = _metadata_for(doc)
    text = _document_text(doc, metadata)

    if isinstance(doc, dict):
        raw_id = _first_non_empty(doc.get("id"), doc.get("doc_id"))
        title = _first_non_empty(doc.get("title"), metadata.get("title"), "Sin título")
        url = _first_non_empty(doc.get("url"), metadata.get("url"))
        source = _first_non_empty(doc.get("source"), metadata.get("source"), "Local")
        score = doc.get("score", metadata.get("score", 0))
        chunk_id = _first_non_empty(doc.get("chunk_id"), metadata.get("chunk_id"))
        chunk_index = doc.get("chunk_index", metadata.get("chunk_index"))
        chunk_total = doc.get("chunk_total", metadata.get("chunk_total"))
    else:
        raw_id = _first_non_empty(getattr(doc, "id", None), metadata.get("doc_id"))
        title = _first_non_empty(metadata.get("title"), "Sin título")
        url = _first_non_empty(metadata.get("url"))
        source = _first_non_empty(metadata.get("source"), "Local")
        score = metadata.get("score", 0)
        chunk_id = _first_non_empty(metadata.get("chunk_id"))
        chunk_index = metadata.get("chunk_index")
        chunk_total = metadata.get("chunk_total")

    document_key = _first_non_empty(url, title, raw_id, metadata.get("source"), f"doc_{fallback_idx}")
    if chunk_id:
        stable_id = chunk_id
    elif chunk_index is not None:
        stable_id = f"{document_key}#chunk-{chunk_index}"
    else:
        stable_id = _first_non_empty(raw_id, f"{document_key}#doc-{fallback_idx}")

    metadata = {
        **metadata,
        "document_key": document_key,
        "chunk_id": chunk_id or stable_id,
        "chunk_index": chunk_index,
        "chunk_total": chunk_total,
    }

    return {
        "id": stable_id,
        "doc_id": raw_id or stable_id,
        "chunk_id": chunk_id or stable_id,
        "document_key": document_key,
        "chunk_index": chunk_index,
        "chunk_total": chunk_total,
        "text": text,
        "content": text,
        "url": url,
        "title": title,
        "source": source,
        "score": score or 0,
        "metadata": metadata,
    }


def _serialize_documents(docs: Iterable[Any]) -> list[Dict[str, Any]]:
    return [_serialize_document(doc, idx) for idx, doc in enumerate(docs or [])]
    
@router.post(
    "",
    response_model=QueryResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Query the RAG system for an answer.
    
    - **query**: User query in Spanish
    - **use_rag**: Whether to use the configurable RAG flow
    - **top_k**: Number of documents to retrieve (1-50)
    - **temperature**: Optional LLM temperature override
    - **relevance_threshold**: Optional relevance threshold override
    - **max_doc_chars**: Optional document truncation limit
    - **use_query_expansion**: Whether to use co-occurrence query expansion
    - **use_internet_search**: Whether to allow internet fallback search
    """
    logger.info(f"query: {request.query} top_k: {request.top_k} use_internet: {request.use_internet_search}")
    if not globals['_rag_pipeline']:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline not initialized",
        )
    
    try:
  
        result = {
            "query": request.query,
            "documents_retrieved": [],
            "top_local_score": 0.0,
    
        }
        
        if request.use_rag:
            result = await globals['_rag_pipeline'].retrieve(
                query=request.query,
                chunker=globals['chunker'],
                top_k=request.top_k,
                use_expand=request.use_query_expansion,
                relevance_threshold=request.relevance_threshold,
                use_internet_search=request.use_internet_search,
            )
        serialized_docs = _serialize_documents(result.get("documents", []))
        import time
        _session_id  = str(time.time())
        _session_store[_session_id] = {
            "original_query": request.query,
            "expanded_query":result.get('expanded_query',''),
            "original_docs": serialized_docs,
            "created_at": __import__('datetime').datetime.now()
        }
        return QueryResponse(
            query=result["query"],
            expanded_query=result.get("expanded_query",""),
            documents_retrieved=serialized_docs,
            top_local_score=result["top_local_score"],
            session_id=_session_id, 
            
        )
    except RAGRetrievalError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Retrieval failed: {exc}",
        )
    except RAGAnswerGenerationError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Answer generation failed: {exc}",
        )
    except RAGPipelineInitializationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Pipeline not properly initialized: {exc}",
        )
    except RAGError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG error: {exc}",
        )
    except WebSearchExecutionError as exc:
        raise HTTPException(
            status_code=500,
            detail=f'no internet: {exc}'
        )
    except Exception as exc:
        logger.error(f"Unexpected error in query endpoint: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {exc}",
        )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid feedback data"},
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def feedback(request: FeedbackRequest) -> FeedbackResponse:
    """
    Apply Rocchio relevance feedback to improve retrieval.
    """
    if not globals.get('_rag_pipeline'):
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")
    
    if not globals.get('_text_normalizer'):
        raise HTTPException(status_code=503, detail="Text normalizer not initialized")
    
    try:
        original_query = request.original_query
        original_docs = []
        
        # Obtener datos de la sesión
        if request.session_id in _session_store:
            session_data = _session_store[request.session_id]
            if not original_query:
                original_query = session_data.get("expanded_query") or session_data.get("original_query")
            original_docs = session_data.get("original_docs", [])
        elif not original_query:
            raise HTTPException(
                status_code=404,
                detail=f"Session {request.session_id} not found and no original_query provided",
            )
        
        relevant_texts = []
        non_relevant_texts = []
        
        doc_map = {}
        for idx, doc in enumerate(original_docs):
            serialized = _serialize_document(doc, idx)
            doc_text = serialized.get("content", "")
            if not doc_text:
                continue
            for doc_id in _document_aliases(serialized):
                doc_map[doc_id] = doc_text
        
        # Clasificar documentos relevantes y no relevantes
        for doc_id in request.relevant_docs:
            if doc_id in doc_map and doc_map[doc_id]:
                relevant_texts.append(doc_map[doc_id])
        
        for doc_id in request.non_relevant_docs:
            if doc_id in doc_map and doc_map[doc_id]:
                non_relevant_texts.append(doc_map[doc_id])
        
        # Aplicar Rocchio
        rocchio = globals.get('rocchio')
        if not rocchio:
            raise HTTPException(status_code=500, detail="Rocchio not initialized")
        
        reformulated_query_weights = rocchio.reformulate(
            original_query=original_query,
            relevant_docs=relevant_texts,
            non_relevant_docs=non_relevant_texts,
        )
        
        top_terms = sorted(
            reformulated_query_weights.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:20]
        
        expanded_query = " ".join([term for term, _ in top_terms])
        
        # Realizar nueva búsqueda
        search_result = await globals['_rag_pipeline'].retrieve(
            query=expanded_query,
            chunker=globals['chunker'],
            top_k=request.top_k,
            use_expand=False,
            relevance_threshold=0.3,
            use_internet_search=False,
        )
        
        # Generar contexto y respuesta
        context = await get_context(search_result.get('documents', []))
        print(original_query)
        answer = await globals['_generator'].generate(context, original_query)
        logger.info(f"Anwser generated")
        serialized_docs = _serialize_documents(search_result.get("documents", []))
        
        if request.session_id in _session_store:
            del _session_store[request.session_id]
        print(answer)
        return FeedbackResponse(
            answer=answer,
            retrieved_docs=serialized_docs,
            reformulated_query=dict(top_terms),
            session_id=request.session_id,
        )
        
    except RAGRetrievalError as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed after feedback: {exc}")
    except RAGAnswerGenerationError as exc:
        raise HTTPException(status_code=500, detail=f"Answer generation failed: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error in feedback endpoint: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}")


async def get_context(docs):
    """Genera contexto a partir de documentos (pueden ser dict o LangChain Document)."""
    if not docs:
        return ""
    
    context_parts = []
    for doc in docs:
        # Extraer texto según el tipo de documento
        if hasattr(doc, 'page_content'):  # LangChain Document
            doc_text = doc.page_content
        elif isinstance(doc, dict):  # Diccionario
            doc_text = doc.get("content") or doc.get("text") or doc.get("page_content", "")
        else:
            continue
        
        if doc_text:
         
            context_parts.append(doc_text)
    
    return "\n".join(context_parts)
