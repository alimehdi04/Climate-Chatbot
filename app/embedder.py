from sentence_transformers import SentenceTransformer
from config import Config
from app.logger import get_logger

logger = get_logger(__name__)

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {Config.EMBEDDING_MODEL}")
        try:
            _model = SentenceTransformer(Config.EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model '{Config.EMBEDDING_MODEL}': {e}")
            raise RuntimeError(f"Embedding model could not be loaded: {e}") from e
    return _model


def embed(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")
    try:
        model = get_model()
        vector = model.encode(text, convert_to_numpy=True)
        logger.debug(f"Embedded text ({len(text)} chars) → vector dim {len(vector)}")
        return vector.tolist()
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise RuntimeError(f"Embedding failed: {e}") from e