from __future__ import annotations

import os
import pickle
from pathlib import Path

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.feature_extraction.text import TfidfVectorizer
import signal
from contextlib import contextmanager

from src.errors.vector_db_errors import (
    EmbeddingModelNotFittedError,
    EmbeddingsModelNotFoundError,
    EmptyDocumentListError,TimeoutError
)
from src.indexing.indexer import TextNormalizer
from src.utils.logger import vector_logger as logger


class TfidfEmbeddings(Embeddings):
    """
    LangChain embedding model using basic TF-IDF vectors.
    """

    def __init__(
        self,
        normalizer: TextNormalizer | None = None,
        max_features: int = 15_000,
    ) -> None:
        self.normalizer = normalizer or TextNormalizer()
        self.max_features = max_features

        self._vectorizer = TfidfVectorizer(
            tokenizer=self.normalizer.normalize,
            max_features=self.max_features,
            token_pattern=None,
            lowercase=False,
            max_df=0.85,
            sublinear_tf=True,
            norm='l2',
            ngram_range=(1,2),
            min_df=1
        )
        self._fitted = False

    def fit(self, documents: list[dict]) -> "TfidfEmbeddings":
        """Fit the TF-IDF model from a list of document dicts."""
        if not documents:
            raise EmptyDocumentListError("Empty document list.")

        logger.info(f"Fitting TF-IDF model on {len(documents)} documents...")
        self._vectorizer.fit(documents)
        self._fitted = True

        v = len(self._vectorizer.vocabulary_)
        logger.info(f"TF-IDF Fitted: {len(documents)} docs | {v} terms")
        return self

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not self._fitted:
            raise EmbeddingModelNotFittedError("TF-IDF embeddings model is not fitted.")
        matrix = self._vectorizer.transform(texts)
        return matrix.toarray().astype(np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        if not self._fitted:
            raise EmbeddingModelNotFittedError("TF-IDF embeddings model is not fitted.")
        vector = self._vectorizer.transform([text])
        return vector.toarray().astype(np.float32).flatten().tolist()

    def save(self, directory: str | Path) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "tfidf_embeddings.pkl", "wb") as fh:
            pickle.dump(self, fh, protocol=pickle.HIGHEST_PROTOCOL)
    def __str__(self):
        return f"TfidfEmbeddings( max_features = {self.max_features})"
    @classmethod
    def load(cls, directory: str | Path) -> "TfidfEmbeddings":
        path = Path(directory) / "tfidf_embeddings.pkl"
        if not path.exists():
            raise EmbeddingsModelNotFoundError(f"Missing embeddings model at {path}")
        with open(path, "rb") as fh:
            return pickle.load(fh)

def is_model_cached(model_name: str) -> bool:
    cache_path = Path('models') / "hf_cache/hub/"
    model_pattern = model_name.replace("/", "--")
    return any(cache_path.glob(f"*{model_pattern}*"))



@contextmanager
def timeout(seconds):
    """Context manager for timeout."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

def get_embeddings(
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    timeout_seconds: int = 30,
) -> Embeddings:
    """
    Factory function to get the improved embedding model with timeout.
    """
    os.environ["HF_HUB_OFFLINE"] = "True"

    if not is_model_cached(model_name):
        del os.environ["HF_HUB_OFFLINE"]

    backend = os.environ.get("GGML_BACKEND", "cpu").lower()
    device = "cuda" if backend in ("cuda", "metal") else "cpu"

    logger.info(f"Loading Transformer model: {model_name} on {device}...")
    
    try:
        with timeout(timeout_seconds):
            return HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": True},
                show_progress=True 
            )
    except TimeoutError as exc:
        logger.error(f"Model loading timed out after {timeout_seconds}s")
        raise EmbeddingsModelNotFoundError(f"Could not load embeddings model: {model_name} (timeout)") from exc
    except Exception as exc:
        logger.error(f"Failed to load HuggingFace embeddings model: {exc}")
        raise EmbeddingsModelNotFoundError(f"Could not load embeddings model: {model_name}") from exc