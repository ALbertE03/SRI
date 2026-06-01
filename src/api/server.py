#!/usr/bin/env python3

import logging
import sys
import time
from src.api.app import app
import uvicorn
from src.api.routes.query import set_dependencies
from src.config import API_HOST, API_PORT, CHUNK_SIZE, CHUNK_OVERLAP, STRATEGY, MIN_CHUNK_SIZE,ALPHA,BETA,GAMMA
from src.indexing.indexer import TextNormalizer, InvertedIndex
from src.indexing.storage import DocumentStore
from src.indexing.chunker import DocumentChunker
from src.retrieval.lm_retriever import LMRetriever
from src.config import \
                CHUNK_SIZE, \
                CHUNK_OVERLAP, \
                STRATEGY, \
                MIN_CHUNK_SIZE,\
                INDEX_LANGUAGE,\
                FORCE,INDEX_SAVE_DIR,DATA_DIR,\
                MU,MAX_FEATURES,BATCH_SIZE,RESET,RAG_RELEVANCE_THRESHOLD,\
                MODEL_TEMPERATURE,MODEL_MAX_TOKENS,MODEL_N_CTX,MODEL_VERBOSE,N_THREADS,N_BATCH,N_GPU_LAYERS
from pathlib import Path             
from src.vector_db.vector_store import VectorStore
from src.vector_db.embeddings import TfidfEmbeddings,get_embeddings
from src.search_internet.searcher import WebSearcher
from src.retrieval.query_processor import QueryProcessor
from src.positioning.ranker import ResultRanker
from src.utils.model_downloader import ModelDownloader
from src.rag.rag import RAGPipeline
from src.feedback.rocchio import RocchioFeedback
from src.generator.answer_generator import AnswerGenerator



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_indenxer=None
_generator=None
_rag_pipeline=None
_text_normalizer=None
_ranker=None
lm_retrieval=None
search_internet=None
stats =None
vector_db =None
chunker=None


async def initialize_components(model_path:str,force:bool=False) -> tuple:
    logger.info("Initializing SRI system...")
    indexes_dir = Path(INDEX_SAVE_DIR)
    
    logger.info("Initializing TextNormalizer")
    normalizer = TextNormalizer(language=INDEX_LANGUAGE)
    logger.info(f"TextNormalizer initialized -> {normalizer}")
    logger.info("Initializing DocumentChunker")
    chunker = DocumentChunker(
        normalizer=normalizer,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        strategy=STRATEGY,
        min_chunk_size=MIN_CHUNK_SIZE
    )
    logger.info(f"DocumentChunker initialized -> {chunker}")
    logger.info("Initializing RocchioFeedback")
    rocchio = RocchioFeedback(
            normalizer=normalizer,
            alpha=ALPHA,
            beta=BETA,
            gamma=GAMMA,
        )
    logger.info(f"RocchioFeedback initialized -> {rocchio}")
    indexer=None
    def get_or_create_system(force: bool = False) -> tuple[VectorStore,LMRetriever]:
        lm_path = indexes_dir / "lm"
        index_path = indexes_dir / "index"
        shared_chunked_docs = None
        embeddings_path = indexes_dir / "vector_store"
        chunked_docs=[]
        def get_chunked_docs():
            nonlocal shared_chunked_docs
            if shared_chunked_docs is None:
                logger.info(f"Loading documents from {DATA_DIR}")
                docs = DocumentStore(DATA_DIR).load_all()
                logger.info(f"Loaded {len(docs)} documents")
                raw_docs = docs.all()
                if not raw_docs:
                    shared_chunked_docs = []
                else:
                    logger.info(f"Chunking {len(raw_docs)} documents...")
                    shared_chunked_docs = chunker.chunk_corpus(raw_docs)
                    logger.info(f"Created {len(shared_chunked_docs)} chunks")
            return shared_chunked_docs   

        if not force and lm_path.exists():
            logger.info("Loading existing LM retriever...")
            lm = LMRetriever.load(lm_path)
            logger.info(f"LM retriever loaded -> {lm}")

        else:
            logger.info("Building new LM retriever...")
            chunked_docs = get_chunked_docs()
            if not chunked_docs:
                logger.warning("No documents found in data/")
                return None, None 
        logger.info(f"Initializing InvertedIndex...")
        if not index_path.exists():
            indexer = InvertedIndex(normalizer=normalizer)
            indexer.build(chunked_docs)
            logger.info(f"InvertedIndex initialized -> {indexer}")
            indexer.save(index_path)
        
        indexer = InvertedIndex.load(index_path)
        lm = LMRetriever.from_inverted_index(indexer, normalizer=normalizer,mu=MU)
        lm.save(lm_path)
        logger.info(f"LMRetriever initialized -> {lm}")
        logger.info("Initializing embeddings and vector store...")

        try:
            
            embeddings = get_embeddings()
            logger.info(f"Transformer embeddings initialized -> {embeddings}")
        except Exception as exc:
            logger.warning(f"Transformer embeddings unavailable, using TF-IDF: {exc}")
            if (embeddings_path / "tfidf_embeddings.pkl").exists():
                logger.info("Loading existing TF-IDF embeddings model...")
                embeddings = TfidfEmbeddings.load(embeddings_path)
                logger.info(f"TF-IDF embeddings loaded -> {embeddings}")
            else:
                logger.info("Initializing new TF-IDF embeddings model...")
                embeddings = TfidfEmbeddings(normalizer=normalizer,max_features=MAX_FEATURES)
                logger.info(f"TF-IDF embeddings initialized -> {embeddings}")
                
                
        logger.info(f"Initializing VectorStore")
        vector_store = VectorStore(embeddings=embeddings)
        logger.info(f"VectorStore initialized -> {vector_store}")

        if (force or vector_store.stats()["num_documents"] == 0) or (isinstance(embeddings,TfidfEmbeddings) and not embeddings._fitted):
           
            chunked_docs = get_chunked_docs()

            if chunked_docs:
                doc_ids = []
                texts = []
                metadata=[]
                
                for chunk in chunked_docs:
                    chunk_id = chunk.get("chunk_id", str(chunk.get("id", "")))
                    doc_ids.append(chunk_id)
                    texts.append(" ".join(chunk.get("tokens", "")))
                    metadata.append({"url":chunk.get("url"," "),"title":chunk.get('title',''),"front_prev":chunk.get("content")})

                if isinstance(embeddings, TfidfEmbeddings):
                    embeddings.fit(texts)
                    embeddings.save(embeddings_path)

                logger.info("Populating vector store with chunks...")
                vector_store.setup(doc_ids, texts,metadata,batch_size=BATCH_SIZE,reset=RESET)
                logger.info(f"Vector store populated with {len(doc_ids)} chunks")
            else:
                logger.warning("No chunks available to populate the vector store.")
        return lm, vector_store

    logger.info("Creating retrieval systems...")
    lm_retriever, vector_store = get_or_create_system(force=force)
    
    logger.info(f"Initializing WebSearcher")
    web_searcher = WebSearcher(normalizer=normalizer)
    logger.info(f"WebSearcher initialized -> {web_searcher}")
    logger.info("Initializing QueryProcessor...")
    query_processor = QueryProcessor(normalizer=normalizer)
    logger.info(f"QueryProcessor initialized -> {query_processor}")
    logger.info("Initializing ResultRanker...")
    ranker = ResultRanker()
    logger.info(f"ResultRanker initialized -> {ranker}")
    logger.info("Initializing RAGpipeline ...")
    rag = RAGPipeline(
            retriever_lm=lm_retriever,
            vector_store=vector_store,
            web_searcher=web_searcher,
            query_processor=query_processor,
            ranker=ranker,
            relevance_threshold=RAG_RELEVANCE_THRESHOLD
        )
    logger.info(f"RAGpipeline initialized -> {rag}")
    logger.info("Initializing Answer Generator...")
    model_path_resolved = str(ModelDownloader.ensure_model_exists(model_path))
    logger.info(f"Using model: {model_path_resolved}")

    generator = AnswerGenerator(
            model_path=model_path_resolved,
            n_ctx=MODEL_N_CTX,
            n_threads=N_THREADS,
            n_gpu_layers=N_GPU_LAYERS, 
            temperature=MODEL_TEMPERATURE,
            verbose=MODEL_VERBOSE,
            n_batch=N_BATCH,
            max_token=MODEL_MAX_TOKENS
        )
    logger.info(f"AnswerGenerator initialized -> {generator}")
    logger.info("✓ SRI system initialized successfully")
    return indexer,generator,rag,normalizer,ranker,lm_retrieval,search_internet,vector_db,chunker,rocchio

async def _init_app(_indenxer, _generator,  
                _rag_pipeline, _text_normalizer, 
                _ranker, lm_retrieval, search_internet, 
                 vector_db,chunker,rocchio)->None:
                globals = {
                '_indenxer':_indenxer,
                '_generator':_generator,
                '_rag_pipeline':_rag_pipeline,
                '_text_normalizer':_text_normalizer,
                '_ranker':_ranker,
                'lm_retrieval':lm_retrieval,
                'search_internet':search_internet,
                'vector_db':vector_db,
                'chunker':chunker,
                "rocchio":rocchio
                }
                set_dependencies(globals)
                
  
async def main(model_path):
    """Main entry point."""
    try:
        async def run():
            t = time.time()
            _indenxer, _generator, _rag_pipeline, _text_normalizer, _ranker, lm_retrieval, search_internet, vector_db,chunker,rocchio = await initialize_components(model_path,force=FORCE)
            await _init_app(_indenxer, _generator, _rag_pipeline, _text_normalizer, _ranker, lm_retrieval, search_internet, vector_db,chunker,rocchio)
            config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="info")
            server = uvicorn.Server(config)
            logger.info("✓ API initialized successfully")
            logger.info("Starting FastAPI server...")
            logger.info("API available at: http://localhost:8000")
            logger.info("Docs available at: http://localhost:8000/docs")
            logger.info(f"Initialization completed in {time.time() - t:.2f} seconds")
            await server.serve()
            
        await run()
       

    except Exception as exc:
        logger.error(f"Fatal error: {exc}", exc_info=True)
        sys.exit(1)

