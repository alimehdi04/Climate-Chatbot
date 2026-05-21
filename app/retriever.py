import chromadb
from config import Config
from app.embedder import embed
from app.logger import get_logger

logger = get_logger(__name__)

_collection = None


def get_collection():
    global _collection

    if _collection is None:
        logger.info(f"Connecting to ChromaDB at {Config.CHROMA_PATH}")

        try:
            chroma_client = chromadb.PersistentClient(
                path=Config.CHROMA_PATH
            )

            _collection = chroma_client.get_collection(
                Config.CHROMA_COLLECTION
            )

            count = _collection.count()

            logger.info(
                f"ChromaDB collection "
                f"'{Config.CHROMA_COLLECTION}' loaded "
                f"— {count} chunks"
            )

        except Exception as e:
            logger.error(
                f"Failed to load ChromaDB collection "
                f"'{Config.CHROMA_COLLECTION}': {e}"
            )

            raise RuntimeError(
                "Vector database not found or invalid. "
                "Please run ingest.py first."
            ) from e

    return _collection


def retrieve(query: str) -> list[dict]:

    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    logger.info(
        f"Retrieving chunks for query: "
        f"'{query[:80]}...'"
        if len(query) > 80
        else f"Retrieving chunks for query: '{query}'"
    )

    # Generate embedding
    try:
        query_vector = embed(query)

    except RuntimeError as e:
        logger.error(
            f"Embedding failed during retrieval: {e}"
        )
        raise

    # Query ChromaDB
    try:
        collection = get_collection()

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=Config.TOP_K,
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

    except RuntimeError:
        raise

    except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")

        raise RuntimeError(
            f"Vector search failed: {e}"
        ) from e

    passages = []

    all_results = list(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ))

    for doc, meta, dist in all_results:

        if dist < Config.DISTANCE_THRESHOLD:

            passages.append({
                "document": doc,
                "section_number": meta.get(
                    "section_number", ""
                ),
                "section_title": meta.get(
                    "section_title", ""
                ),
                "distance": dist
            })

    # Fallback if no chunks under threshold
    if not passages:

        logger.warning(
            f"No chunks below threshold "
            f"{Config.DISTANCE_THRESHOLD}. "
            f"Using top {len(all_results)} results "
            f"as fallback."
        )

        passages = [
            {
                "document": doc,
                "section_number": meta.get(
                    "section_number", ""
                ),
                "section_title": meta.get(
                    "section_title", ""
                ),
                "distance": dist
            }

            for doc, meta, dist in all_results
        ]

    distances = [p["distance"] for p in passages]

    logger.info(
        f"Retrieved {len(passages)} chunks — "
        f"distance range: "
        f"{min(distances):.3f}–"
        f"{max(distances):.3f}"
    )

    return passages