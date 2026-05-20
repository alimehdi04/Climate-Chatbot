import uuid
import json
import redis
from config import Config
from app.logger import get_logger

logger = get_logger(__name__)

try:
    client = redis.from_url(Config.REDIS_URL, decode_responses=True, socket_timeout=5)
    client.ping()
    logger.info(f"Redis connected at {Config.REDIS_URL}")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Redis connection failed at startup: {e}")
    client = None


def _get_client():
    """Return Redis client or raise a clean error if unavailable."""
    if client is None:
        raise RuntimeError("Redis is unavailable. Please ensure Redis is running.")
    try:
        client.ping()
    except redis.exceptions.ConnectionError as e:
        raise RuntimeError(f"Redis connection lost: {e}") from e
    return client


def create_session() -> str:
    r = _get_client()
    session_id = str(uuid.uuid4())
    key = f"session:{session_id}"
    try:
        r.set(key, json.dumps([]), ex=Config.SESSION_TTL)
        logger.info(f"Session created: {session_id}")
        return session_id
    except redis.exceptions.RedisError as e:
        logger.error(f"Failed to create session: {e}")
        raise RuntimeError(f"Could not create session: {e}") from e


def get_history(session_id: str) -> list:
    r = _get_client()
    key = f"session:{session_id}"
    try:
        data = r.get(key)
        if data is None:
            logger.warning(f"Session not found or expired: {session_id}")
            return []
        return json.loads(data)
    except redis.exceptions.RedisError as e:
        logger.error(f"Failed to read session {session_id}: {e}")
        return []  # graceful fallback — continue without history
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted session data for {session_id}: {e}")
        return []


def append_turn(session_id: str, user_msg: str, assistant_msg: str):
    r = _get_client()
    try:
        history = get_history(session_id)
        history.append({"role": "user",      "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        history = history[-20:]  # keep last 10 turns
        key = f"session:{session_id}"
        r.set(key, json.dumps(history), ex=Config.SESSION_TTL)
        logger.debug(f"Session {session_id} updated — {len(history)} messages stored")
    except redis.exceptions.RedisError as e:
        # Non-fatal — answer was already generated, just log and continue
        logger.error(f"Failed to persist turn for session {session_id}: {e}")


def delete_session(session_id: str):
    r = _get_client()
    try:
        r.delete(f"session:{session_id}")
        logger.info(f"Session deleted: {session_id}")
    except redis.exceptions.RedisError as e:
        logger.error(f"Failed to delete session {session_id}: {e}")


def session_exists(session_id: str) -> bool:
    try:
        r = _get_client()
        exists = r.exists(f"session:{session_id}") == 1
        return exists
    except RuntimeError:
        # If Redis is down, we can't validate sessions
        raise