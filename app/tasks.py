import redis as redis_lib
from celery import Celery
from config import Config
from app.logger import get_logger

logger = get_logger(__name__)

celery_app = Celery(
    "tasks",
    broker=Config.REDIS_URL,
    backend=Config.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,  # results kept in Redis for 1 hour
)


@celery_app.task(bind=True, max_retries=0)
def process_chat(self, session_id: str, user_message: str) -> dict:
    from app.retriever import retrieve
    from app.llm import generate
    from app.session import get_history, append_turn

    logger.info(f"Task started — session: {session_id} | message: '{user_message[:60]}'")

    # Step 1 — Retrieve relevant passages
    try:
        passages = retrieve(user_message)
    except ValueError as e:
        logger.error(f"Invalid query in task: {e}")
        return {"status": "error", "answer": str(e), "sources": []}
    except RuntimeError as e:
        logger.error(f"Retrieval failed in task: {e}")
        return {"status": "error", "answer": str(e), "sources": []}

    # Step 2 — Fetch conversation history
    try:
        history = get_history(session_id)
    except RuntimeError as e:
        logger.warning(f"Could not fetch history for {session_id}: {e} — proceeding without history")
        history = []  # non-fatal, continue without history

    # Step 3 — Call Ollama
    try:
        answer = generate(passages, history, user_message)
    except RuntimeError as e:
        logger.error(f"LLM generation failed in task: {e}")
        return {"status": "error", "answer": str(e), "sources": []}

    # Step 4 — Persist turn to session (non-fatal if it fails)
    try:
        append_turn(session_id, user_message, answer)
    except Exception as e:
        logger.warning(f"Could not save turn to session {session_id}: {e}")

    sources = [
        {
            "section_number": p["section_number"],
            "section_title":  p["section_title"]
        }
        for p in passages
    ]

# Only return sources if chunks were within threshold (not fallback results)
# sources = [
#     {
#         "section_number": p["section_number"],
#         "section_title":  p["section_title"]
#     }
#     for p in passages
#     if p["distance"] < Config.DISTANCE_THRESHOLD
# ]

    logger.info(f"Task complete — session: {session_id} | answer: {len(answer)} chars | sources: {len(sources)}")
    return {"status": "done", "answer": answer, "sources": sources}