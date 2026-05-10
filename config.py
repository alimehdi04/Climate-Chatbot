import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY         = os.getenv("SECRET_KEY", "dev-secret")
    DEBUG              = os.getenv("FLASK_DEBUG", "1") == "1"

    # Redis
    REDIS_URL          = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ChromaDB
    CHROMA_PATH        = os.getenv("CHROMA_PATH", "./chroma_db")
    CHROMA_COLLECTION  = os.getenv("CHROMA_COLLECTION", "climate_academy")

    # Embedding
    EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Ollama
    OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # Chunking
    CHUNK_SIZE         = int(os.getenv("CHUNK_SIZE", 150))
    CHUNK_OVERLAP      = int(os.getenv("CHUNK_OVERLAP", 30))

    # Retrieval
    TOP_K              = int(os.getenv("TOP_K", 5))
    DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD", 0.7))

    # Session
    SESSION_TTL        = int(os.getenv("SESSION_TTL_SECONDS", 86400))