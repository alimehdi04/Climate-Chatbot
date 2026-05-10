import chromadb
from pathlib import Path
from config import Config
from html_sectioning import parse_html_path_to_chunks

def run_ingestion():
    print("Starting ingestion...")

    chunks = parse_html_path_to_chunks(
        path=Path("input/sample_ca_book.html"),
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP
    )
    print(f"Total chunks to embed: {len(chunks)}")

    from app.embedder import embed

    chroma_client = chromadb.PersistentClient(path=Config.CHROMA_PATH)

    # Wipe and recreate collection for clean re-ingestion
    try:
        chroma_client.delete_collection(Config.CHROMA_COLLECTION)
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=Config.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]

        ids       = [f"{c.section_number}_{c.chunk_index}_{i+j}" for j, c in enumerate(batch)]
        documents = [c.document for c in batch]
        embeddings = [embed(c.document) for c in batch]
        metadatas = [
            {
                "section_number": c.section_number,
                "section_title":  c.section_title,
                "chunk_index":    c.chunk_index
            }
            for c in batch
        ]

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        print(f"  Indexed chunks {i+1} to {min(i+batch_size, len(chunks))}")

    print(f"\nIngestion complete. Total chunks indexed: {collection.count()}")


if __name__ == "__main__":
    run_ingestion()