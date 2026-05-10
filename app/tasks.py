import json
import redis
from celery import Celery
from config import Config

celery_app = Celery(
    "tasks",
    broker=Config.REDIS_URL,
    backend=Config.REDIS_URL
)

redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)


@celery_app.task(bind=True)
def process_chat(self, session_id: str, user_message: str) -> dict:
    from app.retriever import retrieve
    from app.llm import generate
    from app.session import get_history, append_turn

    try:
        # Step 1 — retrieve relevant passages
        passages = retrieve(user_message)

        # Step 2 — fetch conversation history
        history = get_history(session_id)

        # Step 3 — call Ollama
        answer = generate(passages, history, user_message)

        # Step 4 — persist turn to session
        append_turn(session_id, user_message, answer)

        return {
            "status": "done",
            "answer": answer,
            "sources": [
                {
                    "section_number": p["section_number"],
                    "section_title":  p["section_title"]
                }
                for p in passages
            ]
        }

    except Exception as exc:
        return {
            "status": "error",
            "answer": f"Something went wrong: {str(exc)}",
            "sources": []
        }