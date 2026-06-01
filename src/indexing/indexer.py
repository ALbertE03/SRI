from __future__ import annotations

from datetime import datetime
import json
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path
import nltk
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer,WordNetLemmatizer
from nltk.tokenize import word_tokenize

from src.errors.indexing_errors import (
    IndexLoadError,
    IndexPersistenceError,
    InvalidDocumentError,
    
)
from src.utils.logger import indexing_logger as logger
import emoji




# Stop-words: Spanish
_STOP_WORDS: frozenset[str] = frozenset(stopwords.words("spanish"))


class TextNormalizer:
    """
    Converts raw text into a list of normalised tokens.

    Pipeline
    --------
    1. Lowercase
    2. Remove URLs, HTML remnants and non-alphanumeric characters
    3. Tokenize (NLTK punkt)
    4. Remove stop-words (es)
    """

    def __init__(self, language: str = "spanish") -> None:
        self.language = language
        self._stemmer = SnowballStemmer(language)
        #self._lem = WordNetLemmatizer()

    def normalize(self, text: str, stem: bool = False, stopw: bool = True) -> list[str]:
        """Return a list of normalised tokens from *text*."""
        if not text:
            return []
        # lowercase
        text = text.lower().replace("("," ").replace(")"," ").replace("|"," ").replace("`"," ").replace(":"," ").replace(", "," ").replace("''"," ")

        # strip URLs
        text = re.sub(r"https?://\S+|www\.\S+", " ", text)
        text = re.sub(r"\.\.\."," ",text)
        # strip non-alphanumeric (keep letters, digits and spaces)
        text = re.sub(r"[^a-záéíóúüñ\w\s-]", " ", text, flags=re.UNICODE)
        # remove emojis
        text = emoji.replace_emoji(text, replace="")
        text = re.sub(r"\s+", " ", text).strip()
        # tokenize
        tokens = word_tokenize(text, language="spanish")

        # stem
        if stem:
            tokens = [self._stemmer.stem(t) for t in tokens]

        if stopw:
            #stop-words
            tokens = [t for t in tokens if t not in _STOP_WORDS]

        return tokens

    def normalize_query(self, query: str) -> list[str]:
        """Normalise a user query."""
        return self.normalize(query,stem=True,stopw=True)
    def __str__(self) -> str:
        return f"TextNormalizer(language={self.language})"

class InvertedIndex:
    """
    Inverted index with TF-IDF document vectors.

    Internal data structures
    ------------------------
    _index     : dict[term, dict[doc_id, tf]]
                 Posting list: term → {doc_id: raw term frequency}
    _doc_info  : dict[doc_id, dict]
                 Per-document metadata (length, title, url, …)
    _vocab     : set[str]    all indexed terms
    _N         : int         total number of documents indexed
    """

    INDEX_FILE = "inverted_index.pkl"
    META_FILE = "index_meta.json"

    def __init__(
        self,
        normalizer: TextNormalizer = None,
    ) -> None:
        self.normalizer = normalizer 
    

        self._index: dict[str, dict[str, int]] = defaultdict(dict)
        self._doc_info: dict[str, dict] = {}
        self._N: int = 0
        self._vocab: set[str] = set()

    def build(self, documents: list[dict]) -> None:
        """
        Build the index from documents.
        """
        self._index = defaultdict(dict)
        self._doc_info = {}
        self._N = 0
        
        logger.info(f"Building index from {len(documents)} documents...")

        for i,doc in enumerate( documents):
            if not isinstance(doc, dict):
                raise InvalidDocumentError(
                    "Each indexed document must be a dictionary."
                )
            if i%500==0:
                logger.info(f"{i}/{len(documents)}")
            
            doc_id = str(doc.get("chunk_id") or {datetime.now().isoformat()} or doc.get("id") or doc.get("url", "doc_" + str(i)))
            title = doc.get("title", "") or ""
            content = doc.get("content", "") or ""
            if not doc_id:
                raise InvalidDocumentError(
                    "Each document must define either 'id' or 'chunk_id' or 'url'."
                )

            text = title + " " + content

            #tokens = self.normalizer.normalize(text,stopw=True, stem=True)
            tokens = doc.get("tokens",[])
            if not tokens:
                continue

            tf = Counter(tokens)
            doc_length = len(tokens)

            for term, count in tf.items():
                self._index[term][doc_id] = count

            self._doc_info[doc_id] = {
                "length": doc_length,
                "title": title,
                "content_preview": " ".join(tokens),
                "url": doc.get("url", ""),
                "source": doc.get("source", ""),
                "date": doc.get("date", ""),
                "author": doc.get("author", ""),
                "front_prew":content
            }
            self._N += 1

        self._vocab = set(self._index.keys())
        logger.info(f"Built index: {self._N} documents, {len(self._vocab)} terms")
     
    def save(self, directory: str | Path) -> None:
        """Persist the index to *directory* (created if absent)."""
        path = Path(directory)
        try:
            path.mkdir(parents=True, exist_ok=True)

            with open(path / self.INDEX_FILE, "wb") as fh:
                pickle.dump(
                    {
                        "index": dict(self._index),
                        "doc_info": self._doc_info,
                        "N": self._N,
                    },
                    fh,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )

            meta = {
                "num_documents": self._N,
                "vocabulary_size": len(self._vocab),
            }
            with open(path / self.META_FILE, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            raise IndexPersistenceError(f"Failed to persist index to {path}") from exc

        logger.info(
            f"Saved: {self._N} docs, {len(self._vocab)} terms → {path}"
        )

    @classmethod
    def load(cls, directory: str | Path) -> "InvertedIndex":
        """Load a previously saved index from *directory*."""
        path = Path(directory)
        try:
            with open(path / cls.INDEX_FILE, "rb") as fh:
                data = pickle.load(fh)

            idx = cls()
            idx._index = defaultdict(dict, data["index"])
            idx._doc_info = data["doc_info"]
            idx._N = data["N"]
            idx._vocab = set(idx._index.keys())
            return idx
        except Exception as exc:
            raise IndexLoadError(f"Failed to load index from {path}") from exc

    def __repr__(self) -> str:
        return f"InvertedIndex(docs={self._N}, " f"vocab={len(self._vocab)})"
    def __str__(self) -> str:
        return f"InvertedIndex(docs={self._N}, " f"vocab={len(self._vocab)})"
    def stats(self) -> dict:
        """Return a summary dict of index statistics."""
        return {
            "num_documents": self._N,
            "vocabulary_size": len(self._vocab),
        }
