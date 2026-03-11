from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Iterator


class DocumentStore:
    """
    Flat in-memory document store backed by JSONL files on disk.

    Documents are loaded from the standard data layout produced by
    JsonStoragePipeline:

        <data_dir>/
            mobile/   *.jsonl
            pc/       *.jsonl
            general/  *.jsonl

    Each document gets a stable ``id`` field (URL if present, otherwise a
    deterministic hash-based UUID so repeated loads give the same IDs).
    """

    CATEGORIES = ("mobile", "pc", "general")

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._docs: dict[str, dict] = {}   # id → doc

    def load_all(self) -> "DocumentStore":
        """Load every JSONL file found under *data_dir*."""
        for category in self.CATEGORIES:
            self.load_category(category)
        return self

    def load_category(self, category: str) -> "DocumentStore":
        """Load all JSONL files from *data_dir/<category>/*."""
        cat_dir = self.data_dir / category
        if not cat_dir.exists():
            return self

        for jsonl_file in sorted(cat_dir.glob("*.jsonl")):
            self._load_file(jsonl_file, category=category)
        return self

    def _load_file(self, path: Path, category: str) -> None:
        """Parse a single JSONL file and add documents to the store."""
        with open(path, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"[DocumentStore] JSON error {path}:{line_no}: {exc}")
                    continue

                doc = self._normalise(raw, category=category)
                self._docs[doc["id"]] = doc

    @staticmethod
    def _normalise(raw: dict, category: str) -> dict:
        """
        Convert a raw Scrapy item dict into a canonical document dict.

        Canonical schema
        ----------------
        id          str   unique identifier (URL preferred)
        url         str
        title       str
        content     str
        author      str | None
        date        str | None   ISO-8601
        scraped_at  str | None   ISO-8601
        source      str
        tags        list[str]
        category    str          "mobile" | "pc" | "general"
        brand       str | None
        os          str | None
        device_name str | None
        article_type str | None
        metadata    dict
        """
        url = raw.get("url", "")
        doc_id = url if url else str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(raw, sort_keys=True)))

        return {
            "id":          doc_id,
            "url":         url,
            "title":       raw.get("title") or "",
            "content":     raw.get("content") or "",
            "author":      raw.get("author"),
            "date":        raw.get("date"),
            "scraped_at":  raw.get("scraped_at"),
            "source":      raw.get("source", ""),
            "tags":        raw.get("tags") or [],
            "category":    category,
            "subcategory": raw.get("category") or "",
            "brand":       raw.get("brand"),
            "os":          raw.get("os"),
            "device_name": raw.get("device_name"),
            "article_type": raw.get("article_type"),
            "metadata":    raw.get("metadata") or {},
        }


    def get_by_id(self, doc_id: str) -> dict | None:
        """Return the document with the given *doc_id* or None."""
        return self._docs.get(doc_id)

    def get_by_category(self, category: str) -> list[dict]:
        """Return all documents in the given *category*."""
        return [d for d in self._docs.values() if d["category"] == category]

    def all(self) -> list[dict]:
        """Return all documents as a list."""
        return list(self._docs.values())

    def iter(self) -> Iterator[dict]:
        """Yield every document."""
        yield from self._docs.values()

    def __len__(self) -> int:
        return len(self._docs)

    def __repr__(self) -> str:
        cats = {c: len(self.get_by_category(c)) for c in self.CATEGORIES}
        return f"DocumentStore(total={len(self)}, by_category={cats})"


    def save_snapshot(self, path: str | Path) -> None:
        """Write all documents to a single JSONL snapshot file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            for doc in self._docs.values():
                fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
        print(f"[DocumentStore] Snapshot saved: {len(self)} docs → {path}")

    @classmethod
    def from_snapshot(cls, path: str | Path) -> "DocumentStore":
        """Load a store from a previously saved snapshot file."""
        store = cls.__new__(cls)
        store.data_dir = Path(path).parent
        store._docs = {}
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    doc = json.loads(line)
                    store._docs[doc["id"]] = doc
        return store