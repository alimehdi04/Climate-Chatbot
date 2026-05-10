import uuid
import json
import redis
from config import Config

client = redis.from_url(Config.REDIS_URL, decode_responses=True)

def create_session() -> str:
    session_id = str(uuid.uuid4())
    key = f"session:{session_id}"
    client.set(key, json.dumps([]), ex=Config.SESSION_TTL)
    return session_id


def get_history(session_id: str) -> list:
    key = f"session:{session_id}"
    data = client.get(key)
    if data is None:
        return []
    return json.loads(data)


def append_turn(session_id: str, user_msg: str, assistant_msg: str):
    history = get_history(session_id)
    history.append({"role": "user",      "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})
    # Keep only last 10 turns (20 messages)
    history = history[-20:]
    key = f"session:{session_id}"
    client.set(key, json.dumps(history), ex=Config.SESSION_TTL)


def delete_session(session_id: str):
    client.delete(f"session:{session_id}")


def session_exists(session_id: str) -> bool:
    return client.exists(f"session:{session_id}") == 1