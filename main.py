import sys
import argparse
from pathlib import Path
from src.indexing.indexer import InvertedIndex
from src.retrieval.lsi_retriever import LSIRetriever
from src.retrieval.query_processor import QueryProcessor


def build_vector_index():
    print(f"\n[VectorIndexer] Building Vector Store (LSI)...")

    index_path = Path("indexes/index")
    if not index_path.exists():
        print(
            f"[VectorIndexer] Error: Inverted index not found at {index_path}. Build it first."
        )
        sys.exit(1)

    print(f"[VectorIndexer] Loading inverted index from {index_path}...")
    try:
        idx = InvertedIndex.load(index_path)
    except Exception as e:
        print(f"[VectorIndexer] Error loading index: {e}")
        sys.exit(1)

    print(f"[VectorIndexer] Index loaded: {idx}")

    n_docs = idx.stats()["num_documents"]
    if n_docs < 2:
        print(f"[VectorIndexer] Error: Not enough documents ({n_docs}) to build LSI.")
        sys.exit(1)

    n_components = min(200, n_docs - 1)

    print(f"[VectorIndexer] Fitting LSI with {n_components} components...")
    lsi = LSIRetriever.from_inverted_index(idx, n_components=n_components)

    output_path = Path("indexes/lsi")
    lsi.save(output_path)

    print(f"[VectorIndexer] Vector Store built and saved to {output_path}.\n")


def run_query_interface():
    print(f"\n[Search] Starting interactive search interface...")

    lsi_path = Path("indexes/lsi")
    if not (lsi_path / "vector_store.pkl").exists():
        print(f"[Search] Error: Vector Store not found at {lsi_path}. Run build first.")
        return

    lsi = LSIRetriever.load(lsi_path)
    qp = QueryProcessor()

    print(f"[Search] Model loaded. Type 'exit' to quit.\n")

    while True:
        try:
            query = input("Query> ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                break

            # Process query
            pq = qp.process(query)

            # Retrieve
            results = lsi.retrieve(pq.text, top_k=5)

            print(f"\nResults for: '{pq.text}'")
            if not results:
                print("No relevant documents found.")
            else:
                for r in results:
                    print(f"  [{r['score']:.4f}] {r['title']} ({r['date'][:10]})")
                    print(f"    URL: {r['url']}")
            print("-" * 40)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="SRI Vector DB and Search Interface")
    parser.add_argument("--build", action="store_true", help="Build the vector store")
    parser.add_argument(
        "--query", action="store_true", help="Start the search interface"
    )

    args = parser.parse_args()

    if args.build:
        build_vector_index()
    elif args.query:
        run_query_interface()
    else:
        if (Path("indexes/lsi") / "vector_store.pkl").exists():
            run_query_interface()
        else:
            build_vector_index()


if __name__ == "__main__":
    main()
