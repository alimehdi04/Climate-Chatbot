import chromadb
from config import Config
from app.embedder import embed

_collection = None

def get_collection():
    global _collection
    if _collection is None:
        chroma_client = chromadb.PersistentClient(path=Config.CHROMA_PATH)
        _collection = chroma_client.get_collection(Config.CHROMA_COLLECTION)
    return _collection


def retrieve(query: str) -> list[dict]:
    query_vector = embed(query)
    collection = get_collection()

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=Config.TOP_K,
        include=["documents", "metadatas", "distances"]
    )

    passages = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        if dist < Config.DISTANCE_THRESHOLD:
            passages.append({
                "document": doc,
                "section_number": meta.get("section_number", ""),
                "section_title":  meta.get("section_title", ""),
                "distance":       dist
            })

    # Fallback — return top results even if all exceed threshold
    if not passages:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            passages.append({
                "document": doc,
                "section_number": meta.get("section_number", ""),
                "section_title":  meta.get("section_title", ""),
                "distance":       dist
            })

    return passages