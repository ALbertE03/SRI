"""Document chunker for splitting documents into smaller pieces."""

from typing import Any, List, Dict
import re
from src.indexing.indexer import TextNormalizer

class DocumentChunker:
    """
    Splits documents into smaller chunks for better retrieval.
    
    Strategies:
    - fixed_size: Chunks of fixed number of characters
    - paragraph: Split by paragraphs
    - sliding: Sliding window with overlap
    """
    
    def __init__(
        self,
        normalizer:TextNormalizer,
        chunk_size: int = 1500,
        chunk_overlap: int = 100,
        strategy: str = "sliding",
        min_chunk_size: int = 100,

    ):  
        self.normalizer = normalizer
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.min_chunk_size = min_chunk_size
    
    def chunk_document(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk a single document into smaller pieces.
        
        Args:
            doc: Document with 'content', 'title', 'url', etc.
            normalizer: TextNormalizer instance
            stopw: Whether to filter stop words
            stem: Whether to stem tokens
            
        Returns:
            List of chunked documents
        """
        content = doc.get("content", "")
        
        if not content:
            return [doc]
        
        if self.strategy == "fixed_size":
            return self._chunk_fixed_size(doc, content)
        elif self.strategy == "paragraph":
            return self._chunk_paragraph(doc, content)
        elif self.strategy == "sliding":
            return self._chunk_sliding(doc, content)
        else:
            return [doc]
    
    def _chunk_fixed_size(self, doc: Dict[str, Any], content: str) -> List[Dict[str, Any]]:
        """Chunk by fixed character size."""
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + self.chunk_size
            chunk_text = content[start:end]
            if not chunk_text:
                continue
        
            if len(chunk_text) >= self.min_chunk_size:
                chunk_doc = {
                    **doc,
                    "content": chunk_text,
                    "chunk_id": f"{doc.get('id', 'unknown')}_{start}",
                    "chunk_index": len(chunks),
                    "chunk_total": -1,
                    "tokens":self.normalizer.normalize(chunk_text,stem=True,stopw=True)
                }
                chunks.append(chunk_doc)
            
            start += self.chunk_size
        
        return chunks if chunks else [doc]
    
    def _chunk_paragraph(self, doc: Dict[str, Any], content: str) -> List[Dict[str, Any]]:
        """Chunk by paragraphs."""
        paragraphs = re.split(r'\n\s*\n', content)
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append({
                        **doc,
                        "content": current_chunk.strip(),
                        "chunk_id": f"{doc.get('id', 'unknown')}_{len(chunks)}",
                        "chunk_index": len(chunks),
                        "chunk_total": -1,
                         "tokens":self.normalizer.normalize(chunk_text,stem=True,stopw=True)
                    })
                current_chunk = para + "\n\n"
        
        if current_chunk.strip() and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append({
                **doc,
                "content": current_chunk.strip(),
                "chunk_id": f"{doc.get('id', 'unknown')}_{len(chunks)}",
                "chunk_index": len(chunks),
                "chunk_total": -1,
                "tokens":self.normalizer.normalize(chunk_text,stem=True,stopw=True)
            })
        
        return chunks if chunks else [doc]
    
    def _chunk_sliding(self, doc: Dict[str, Any], content: str) -> List[Dict[str, Any]]:
        """Chunk with sliding window and overlap by words."""
        chunks = []
        words = content.split()
        start = 0
        chunk_idx = 0
        
        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            if len(chunk_words) >= self.min_chunk_size:
                chunk_doc = {
                    **doc,
                    "content": chunk_text,
                    "chunk_id": f"{doc.get('id', 'unknown')}_{chunk_idx}",
                    "chunk_index": chunk_idx,
                    "chunk_start": start,
                    "chunk_end": min(end, len(words)),
                    "tokens":self.normalizer.normalize(chunk_text,stem=True,stopw=True)
                }
                chunks.append(chunk_doc)
                chunk_idx += 1
            
            start += (self.chunk_size - self.chunk_overlap)
        
        if chunks:
            for chunk in chunks:
                chunk["chunk_total"] = chunk_idx
        
        return chunks if chunks else [doc]
    
    def chunk_corpus(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk entire corpus of documents.
        
        Args:
            docs: List of documents
            normalizer: TextNormalizer instance
            stopw: Whether to filter stop words
            stem: Whether to stem tokens
            
        Returns:
            List of chunked documents
        """
        all_chunks = []
        
        for doc in docs:
            if "tv" in doc.get("url",''):
                continue
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)
        
        return all_chunks

    def __str__(self) -> str:
        return f"DocumentChunker(chunk_size={self.chunk_size}, chunk_overlap={self.chunk_overlap}, strategy={self.strategy}, min_chunk_size={self.min_chunk_size})"