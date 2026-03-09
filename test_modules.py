"""
Quick integration test for the indexing and retrieval modules.
Usage:  uv run python test_modules.py
"""
from src.indexing.storage import DocumentStore
from src.indexing.indexer import InvertedIndex, TextNormalizer
from src.retrieval.lsi_retriever import LSIRetriever
from src.retrieval.query_processor import QueryProcessor

SEP = "=" * 60


# ─────────────────────────────────────────────────────────────────────
# 1. DocumentStore
# ─────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  MODULE: src.indexing.storage  →  DocumentStore")
print(SEP)

store = DocumentStore("data")
store.load_all()

docs = store.all()
print(f"  Loaded:  {len(docs)} documents")

categories: dict[str, int] = {}
for d in docs:
    c = d.get("category", "unknown") or "unknown"
    categories[c] = categories.get(c, 0) + 1
print(f"  By category: {categories}")

# Show first doc
sample = docs[0]
title_s = (sample.get("title") or "")[:65]
content_s = (sample.get("content") or "")[:120]
print(f"\n  Sample doc #{0}:")
print(f"    source  : {sample.get('source','')}")
print(f"    category: {sample.get('category','')}")
print(f"    date    : {str(sample.get('date',''))[:10]}")
print(f"    title   : {title_s}")
print(f"    content : {content_s}...")

# Test by-category retrieval
mobile_docs = store.get_by_category("mobile")
print(f"\n  get_by_category('mobile') → {len(mobile_docs)} docs")

# ─────────────────────────────────────────────────────────────────────
# 2. TextNormalizer
# ─────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  MODULE: src.indexing.indexer  →  TextNormalizer")
print(SEP)

norm = TextNormalizer()
raw = "El iPhone 16 Pro tiene la mejor cámara del mercado en 2024"
tokens = norm.normalize(raw)
print(f"  Input : {raw}")
print(f"  Tokens: {tokens}")

# ─────────────────────────────────────────────────────────────────────
# 3. InvertedIndex (BM25) — base para LSI
# ─────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  MODULE: src.indexing.indexer  →  InvertedIndex")
print(SEP)

idx = InvertedIndex(normalizer=norm)
idx.build(docs)
print(f"  {idx}")
idx.save("indexes/bm25")

# ─────────────────────────────────────────────────────────────────────
# 4. LSI Retriever + QueryProcessor (pipeline completo)
# ─────────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  PIPELINE: QueryProcessor → LSIRetriever")
print(SEP)

# Construir LSI reutilizando el índice invertido
n_components = min(20, len(docs) - 1)  # safe for small corpus
lsi = LSIRetriever.from_inverted_index(idx, n_components=n_components)
print(f"  {lsi}")
print(f"  Stats: {lsi.stats()}")
lsi.save("indexes/lsi")

qp = QueryProcessor()

pipeline_queries = [
    "mejores moviles 2025",
    "iphone camara nocturna",
    "smartphone Samsung Galaxy",
    "móvil batería rendimiento",
]

for raw_q in pipeline_queries:
    # 1. QueryProcessor: normaliza, expande sinónimos e infiere categoría
    pq = qp.process(raw_q)
    print(f"\n  Query original : '{pq.original}'")
    print(f"  Query expandida: '{pq.text}'")
    print(f"  Categoría inf. : {pq.category}")
    # 2. LSIRetriever: busca con la query expandida y filtra por categoría
    results = lsi.retrieve(
        pq.text,
        top_k=3,
        category_filter=pq.category,
    )
    print(f"  Resultados ({len(results)}):")
    for r in results:
        print(f"    [{r['score']:.4f}] {r['title'][:60]}")

# Round-trip desde disco
lsi2 = LSIRetriever.load("indexes/lsi")
pq2 = qp.process("Apple iOS chip")
rt = lsi2.retrieve(pq2.text, top_k=2)
print(f"\n  Round-trip load OK: {lsi2}")

print(f"\n{SEP}")
print("  ALL TESTS PASSED")
print(SEP)
