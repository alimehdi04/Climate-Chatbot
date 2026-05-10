from sentence_transformers import SentenceTransformer
from config import Config

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(Config.EMBEDDING_MODEL)
    return _model


def embed(text: str) -> list[float]:
    model = get_model()
    vector = model.encode(text, convert_to_numpy=True)
    return vector.tolist()