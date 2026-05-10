# Climate Chatbot Backend

A Retrieval-Augmented Generation API for the Climate Academy student book.
Built with Flask, Celery, Redis, ChromaDB, Sentence Transformers, and Ollama.

## Stack
- **Flask + Gunicorn** — REST API
- **Celery + Redis** — async task queue and session store
- **ChromaDB** — vector database
- **all-MiniLM-L6-v2** — local embeddings
- **Ollama (Llama 3.1 8B)** — local LLM inference

## Setup

### 1. Install dependencies
```bash
uv sync
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env if needed
```

### 3. Pull the LLM model
```bash
ollama pull llama3.1:8b
```

### 4. Run ingestion
```bash
uv run python ingest.py
```

### 5. Start services

Terminal 1 — Flask:
```bash
uv run python run.py
```

Terminal 2 — Celery:
```bash
uv run celery -A app.tasks worker --concurrency=2 --loglevel=info
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | /health | Health check |
| POST | /session | Create a new session |
| DELETE | /session/<id> | Clear a session |
| POST | /chat | Send a message (returns task_id) |
| GET | /result/<task_id> | Poll for result |