import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

def _get_env_bool(key: str, default: bool = False) -> bool:
    """Parse boolean environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_env_int(key: str, default: int) -> int:
    """Parse integer environment variable."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_env_float(key: str, default: float) -> float:
    """Parse float environment variable."""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_env_str(key: str, default: str = "") -> str:
    """Get string environment variable."""
    return os.getenv(key, default)


# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
INDEXES_DIR = BASE_DIR / "indexes"
DATA_DIR = BASE_DIR / "data"

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# Default model URL for HuggingFace download
DEFAULT_MODEL_HF_REPO = _get_env_str("MODEL_PATH","lm-kit/llama-3.1-8b-instruct-gguf")
DEFAULT_MODEL_FILE = _get_env_str("MODEL_NAME","Llama-3.1-8B-Instruct-Q4_K_S.gguf")
DEFAULT_MODEL_URL = f"https://huggingface.co/{DEFAULT_MODEL_HF_REPO}/resolve/main/{DEFAULT_MODEL_FILE}".lower()

# Model path or HuggingFace repo ID. Empty downloads the default model.
MODEL_PATH = _get_env_str("MODEL_PATH", "")

# LLM parameters
MODEL_TEMPERATURE = _get_env_float("MODEL_TEMPERATURE", 0.3)
MODEL_MAX_TOKENS = _get_env_int("MODEL_MAX_TOKENS", 200)
MODEL_N_CTX = _get_env_int("MODEL_N_CTX", 2048)
MODEL_VERBOSE = _get_env_bool("MODEL_VERBOSE", False)
N_BATCH = _get_env_int("N_BATCH",64)
N_THREADS=_get_env_int("N_THREADS",8)
N_GPU_LAYERS=_get_env_bool("N_GPU_LAYERS",-1)
# ============================================================================
# RAG CONFIGURATION
# ============================================================================

# Relevance threshold for triggering web search
RAG_RELEVANCE_THRESHOLD = _get_env_float("RAG_RELEVANCE_THRESHOLD", 0.5)

# Query expansion settings
RAG_ENABLE_QUERY_EXPANSION = _get_env_bool("RAG_ENABLE_QUERY_EXPANSION", True)
RAG_QUERY_EXPANSION_TERMS = _get_env_int("RAG_QUERY_EXPANSION_TERMS", 10)
RAG_COOCCURRENCE_WINDOW = _get_env_int("RAG_COOCCURRENCE_WINDOW", 1)

# Retriever weights (LM vs Vector)
RAG_LM_RETRIEVER_WEIGHT = _get_env_float("RAG_LM_RETRIEVER_WEIGHT", 0.5)
RAG_VECTOR_RETRIEVER_WEIGHT = _get_env_float("RAG_VECTOR_RETRIEVER_WEIGHT", 0.5)

# Number of documents to retrieve
RAG_RETRIEVER_K = _get_env_int("RAG_RETRIEVER_K", 10)

# ============================================================================
# VECTOR DB CONFIGURATION
# ============================================================================

VECTOR_DB_COLLECTION_NAME = _get_env_str(
    "VECTOR_DB_COLLECTION_NAME", "sri_documents_transformer"
)
VECTOR_DB_PERSIST_DIR = str((INDEXES_DIR / "chroma_langchain").absolute())
VECTOR_DB_TOP_K = _get_env_int("VECTOR_DB_TOP_K", 10)
BATCH_SIZE = _get_env_int("BATCH_SIZE", 1000)
RESET = _get_env_bool("RESET", False)

# ============================================================================
# WEB SEARCH CONFIGURATION
# ============================================================================

WEB_SEARCH_ENGINE = _get_env_str("WEB_SEARCH_ENGINE", "all")
WEB_SEARCH_MAX_RESULTS = _get_env_int("WEB_SEARCH_MAX_RESULTS", 3)
WEB_SEARCH_REGION = _get_env_str("WEB_SEARCH_REGION", "es-es")
WEB_SEARCH_TIME = _get_env_str("WEB_SEARCH_TIME", "y")

# ============================================================================
# API CONFIGURATION
# ============================================================================

API_HOST = _get_env_str("API_HOST", "0.0.0.0")
API_PORT = _get_env_int("API_PORT", 8000)
FORCE = _get_env_bool("FORCE", False)

# ============================================================================
# INDEXING CONFIGURATION
# ============================================================================
CHUNK_SIZE = _get_env_int("CHUNK_SIZE", 500)
CHUNK_OVERLAP = _get_env_int("CHUNK_OVERLAP", 100)
STRATEGY = _get_env_str("STRATEGY", "sliding")
MIN_CHUNK_SIZE = _get_env_int("MIN_CHUNK_SIZE", 100)

INDEX_LANGUAGE = _get_env_str("INDEX_LANGUAGE", "spanish")
INDEX_SAVE_DIR = str((INDEXES_DIR).absolute())

# LM retrieval
MU = _get_env_float("MU", 500.0)

# TF-IDF fallback
MAX_FEATURES = _get_env_int("MAX_FEATURES", 384)

# Web content fetching
DEFAULT_TIMEOUT = _get_env_int("DEFAULT_TIMEOUT", 15)

# Rocchio feedback
ALPHA = _get_env_float("ALPHA", 1.0)
BETA = _get_env_float("BETA", 0.75)
GAMMA = _get_env_float("GAMMA", 0.15)
