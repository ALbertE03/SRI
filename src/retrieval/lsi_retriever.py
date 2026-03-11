from __future__ import annotations

import pickle
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, lil_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from src.indexing.indexer import InvertedIndex, TextNormalizer


class LSIRetriever:
    """
    Latent Semantic Indexing retriever for the SRI tech-news corpus.

    Construction requires a fully built :class:`InvertedIndex`; use
    :meth:`from_inverted_index` to create the model — this reuses the
    posting lists already computed by the index, avoiding a second
    tokenisation pass.  Persist the fitted model with :meth:`save` and
    reload it with :meth:`load`.

    Parameters
    ----------
    n_components : int
        Number of latent dimensions (rank-k approximation).  200 is a
        good starting point for corpora of a few thousand documents;
        reduce to 50-100 if the corpus is small (<500 docs).
    normalizer : TextNormalizer | None
        Token normaliser shared with the InvertedIndex pipeline.
    """

    MODEL_FILE = "lsi_model.pkl"
    META_FILE  = "lsi_meta.json"

    def __init__(
        self,
        n_components: int = 200,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self.n_components = n_components
        self.normalizer   = normalizer or TextNormalizer()

        # Fitted state
        self._svd:        TruncatedSVD | None = None
        self._doc_matrix: np.ndarray  | None = None  # (N, k) L2-normalised
        self._vocab:      dict[str, int]      = {}    # term → col index
        self._idf:        np.ndarray  | None = None  # (V,) IDF weights
        self._doc_ids:    list[str]           = []
        self._doc_info:   dict[str, dict]     = {}
        self._N:          int                 = 0


    @classmethod
    def from_inverted_index(
        cls,
        index: "InvertedIndex",
        n_components: int = 200,
    ) -> "LSIRetriever":
        """
        Build an LSI model by reusing the posting lists already computed
        by *index*, avoiding a second tokenisation pass over the corpus.

        The TF weights are derived from the raw term-frequency counts in
        ``InvertedIndex._index`` divided by the per-document lengths stored
        in ``InvertedIndex._doc_info``, exactly reproducing what
        :meth:`build` would compute from the original documents.

        Parameters
        ----------
        index        : a fully built InvertedIndex
        n_components : LSI dimensionality (rank-k SVD approximation)
        """
        obj = cls(n_components=n_components, normalizer=index.normalizer)

        obj._doc_ids = list(index._doc_info.keys())
        obj._doc_info = {
            doc_id: {
                "title":    info.get("title",    ""),
                "url":      info.get("url",      ""),
                "source":   info.get("source",   ""),
                "date":     info.get("date",     ""),
                "tags":     info.get("tags",     []),
                "category": info.get("category", ""),
            }
            for doc_id, info in index._doc_info.items()
        }
        obj._N = index._N

        doc_id_to_row = {doc_id: i for i, doc_id in enumerate(obj._doc_ids)}

        vocab_terms = sorted(index._vocab)
        obj._vocab  = {term: col for col, term in enumerate(vocab_terms)}
        V = len(obj._vocab)
        N = obj._N

        # ---- Sparse TF matrix  (N × V) -----------------------------------
        # index._index[term][doc_id] = raw count
        # index._doc_info[doc_id]["length"] = total token count in doc
        tf_matrix: lil_matrix = lil_matrix((N, V), dtype=np.float32)

        for term, postings in index._index.items():
            col = obj._vocab[term]
            for doc_id, count in postings.items():
                row = doc_id_to_row.get(doc_id)
                if row is None:
                    continue
                doc_len = index._doc_info[doc_id]["length"]
                if doc_len > 0:
                    tf_matrix[row, col] = count / doc_len   # normalised TF

        tf_sparse: csr_matrix = csr_matrix(tf_matrix)

        #  IDF weights  (V,) 
        df = np.array((tf_sparse > 0).sum(axis=0)).flatten().astype(np.float32)
        obj._idf = (np.log((N + 1) / (df + 1)) + 1).astype(np.float32)

        #  TF-IDF + L2 row normalisation 
        tfidf: csr_matrix = tf_sparse.multiply(obj._idf)
        tfidf = normalize(tfidf, norm="l2")

        #  Truncated SVD 
        k = min(n_components, N - 1, V - 1)
        if k < 1:
            raise ValueError(
                f"Too few documents ({N}) or terms ({V}) to fit LSI "
                f"with n_components={n_components}."
            )

        obj._svd = TruncatedSVD(
            n_components=k,
            algorithm="randomized",
            n_iter=5,
            random_state=42,
        )
        doc_lsi: np.ndarray = obj._svd.fit_transform(tfidf)
        obj._doc_matrix = normalize(doc_lsi, norm="l2").astype(np.float32)

        explained = obj._svd.explained_variance_ratio_.sum()
        print(
            f"[LSIRetriever] Built from InvertedIndex: {N} docs | {V} terms | "
            f"{k} LSI components | explained variance: {explained:.3f}"
        )
        return obj

    def _vectorize_query(self, query: str) -> np.ndarray:
        """
        Convert a query string into a TF-IDF vector of shape (1, V).

        Uses the same IDF weights computed during :meth:`build` so that
        the query lives in the same term space as the document matrix.
        """
        tokens = self.normalizer.normalize(query)
        if not tokens or self._idf is None:
            return np.zeros((1, len(self._vocab)), dtype=np.float32)

        V     = len(self._vocab)
        n_tok = len(tokens)
        tf    = Counter(tokens)

        q_vec = np.zeros(V, dtype=np.float32)
        for term, count in tf.items():
            if term in self._vocab:
                q_vec[self._vocab[term]] = count / n_tok  # normalised TF

        # Apply IDF
        q_vec = q_vec * self._idf

        # L2 normalise
        norm = float(np.linalg.norm(q_vec))
        if norm > 0:
            q_vec /= norm

        return q_vec.reshape(1, -1)

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        category_filter: str | None = None,
    ) -> list[dict]:
        """
        Score and rank documents by cosine similarity in the LSI space.

        Parameters
        ----------
        query           : free-text user query (Spanish or English)
        top_k           : number of results to return
        category_filter : restrict results to "mobile", "pc" or "general"

        Returns
        -------
        list of result dicts:
            rank, doc_id, title, url, source, date, category, tags,
            score, snippet
        """
        if self._svd is None or self._doc_matrix is None:
            raise RuntimeError(
                "LSIRetriever has not been fitted. "
                "Call from_inverted_index() or load() first."
            )

        #  Project query into LSI space
        q_tfidf = self._vectorize_query(query)            # (1, V)
        q_lsi   = self._svd.transform(q_tfidf)            # (1, k)

        q_norm = float(np.linalg.norm(q_lsi))
        if q_norm > 0:
            q_lsi /= q_norm

        #  Cosine similarities
        #    _doc_matrix: (N, k) L2-normalised
        #    q_lsi:       (1, k) L2-normalised
        sims: np.ndarray = (self._doc_matrix @ q_lsi.T).flatten()  # (N,)

        #  Rank descending
        ranked_indices = np.argsort(sims)[::-1]

        results: list[dict] = []
        rank = 1
        # Scan up to 3*top_k indices to accommodate category filtering
        for idx in ranked_indices[: max(top_k * 3, top_k + 50)]:
            doc_id = self._doc_ids[int(idx)]
            info   = self._doc_info.get(doc_id, {})

            if category_filter and info.get("category", "") != category_filter:
                continue

            results.append(
                {
                    "rank":     rank,
                    "doc_id":   doc_id,
                    "score":    round(float(sims[int(idx)]), 6),
                    "title":    info.get("title",    ""),
                    "url":      info.get("url",      doc_id),
                    "source":   info.get("source",   ""),
                    "date":     info.get("date",     ""),
                    "tags":     info.get("tags",     []),
                    "category": info.get("category", ""),
                    "snippet":  "",
                }
            )
            rank += 1
            if rank > top_k:
                break

        return results


    def save(self, directory: str | Path) -> None:
        """Persist the fitted LSI model to *directory*."""
        import json

        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        with open(path / self.MODEL_FILE, "wb") as fh:
            pickle.dump(
                {
                    "n_components": self.n_components,
                    "svd":          self._svd,
                    "doc_matrix":   self._doc_matrix,
                    "vocab":        self._vocab,
                    "idf":          self._idf,
                    "doc_ids":      self._doc_ids,
                    "doc_info":     self._doc_info,
                    "N":            self._N,
                },
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        meta = {
            "num_documents":     self._N,
            "vocabulary_size":   len(self._vocab),
            "n_components":      self.n_components,
            "actual_components": int(self._svd.n_components) if self._svd else 0,
            "explained_variance": (
                round(float(self._svd.explained_variance_ratio_.sum()), 4)
                if self._svd is not None else 0.0
            ),
        }
        with open(path / self.META_FILE, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2, ensure_ascii=False)

        print(f"[LSIRetriever] Saved to {path / self.MODEL_FILE}")

    @classmethod
    def load(cls, directory: str | Path) -> "LSIRetriever":
        """Load a previously saved LSI model from *directory*."""
        path = Path(directory)
        model_path = path / cls.MODEL_FILE
        if not model_path.exists():
            raise FileNotFoundError(
                f"LSI model not found at {model_path}. "
            )

        with open(model_path, "rb") as fh:
            data = pickle.load(fh)

        obj               = cls(n_components=data["n_components"])
        obj._svd          = data["svd"]
        obj._doc_matrix   = data["doc_matrix"]
        obj._vocab        = data["vocab"]
        obj._idf          = data["idf"]
        obj._doc_ids      = data["doc_ids"]
        obj._doc_info     = data["doc_info"]
        obj._N            = data["N"]
        return obj

    def __repr__(self) -> str:
        k = self._svd.n_components if self._svd is not None else 0
        ev = (
            round(float(self._svd.explained_variance_ratio_.sum()), 3)
            if self._svd is not None else 0.0
        )
        return (
            f"LSIRetriever(docs={self._N}, "
            f"vocab={len(self._vocab)}, "
            f"components={k}, "
            f"explained_var={ev})"
        )

    def stats(self) -> dict:
        """Return a summary dictionary of model statistics."""
        return {
            "num_documents":     self._N,
            "vocabulary_size":   len(self._vocab),
            "n_components":      self.n_components,
            "explained_variance": (
                round(float(self._svd.explained_variance_ratio_.sum()), 4)
                if self._svd is not None else 0.0
            ),
        }
