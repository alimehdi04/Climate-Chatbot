# app/llm.py
import ollama
import httpx
from config import Config
from app.logger import get_logger

logger = get_logger(__name__)


def build_system_prompt(passages: list[dict]) -> str:
    context_block = "\n\n".join(p["document"] for p in passages)
    return f"""You are a helpful assistant for the Climate Academy student book.
Answer questions strictly based on the provided passages below.
Do not use any outside knowledge. If the answer is not in the passages, say so explicitly.
Cite section numbers inline using the format §x.y.z wherever relevant.
Automatically detect and respond in the same language as the user (English, Hindi, or French).
Use bullet points where appropriate for clarity.

RETRIEVED PASSAGES:
{context_block}"""


def generate(
    passages: list[dict],
    history: list[dict],
    user_message: str
) -> str:
    if not passages:
        logger.warning("generate() called with empty passages list")

    system_prompt = build_system_prompt(passages)
    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": user_message})

    logger.info(
        f"Calling Ollama model '{Config.OLLAMA_MODEL}' — "
        f"{len(passages)} passages, {len(history)} history messages"
    )

    try:
        response = ollama.chat(
            model=Config.OLLAMA_MODEL,
            messages=messages,
            options={"temperature": 0.3}
        )
        answer = response["message"]["content"]
        logger.info(f"Ollama responded — {len(answer)} chars generated")
        return answer

    except ollama.ResponseError as e:
        # Model not found, bad request, etc.
        logger.error(f"Ollama API error (status {e.status_code}): {e.error}")
        if e.status_code == 404:
            raise RuntimeError(
                f"Model '{Config.OLLAMA_MODEL}' not found. "
                f"Run: ollama pull {Config.OLLAMA_MODEL}"
            ) from e
        raise RuntimeError(f"Ollama API error: {e.error}") from e

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to Ollama at {Config.OLLAMA_BASE_URL}: {e}")
        raise RuntimeError(
            f"Cannot connect to Ollama. "
            f"Ensure the SSH tunnel is active and Ollama is running on the GPU server."
        ) from e

    except httpx.TimeoutException as e:
        logger.error(f"Ollama request timed out: {e}")
        raise RuntimeError(
            "Ollama request timed out. The model may be overloaded — please try again."
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error calling Ollama: {e}")
        raise RuntimeError(f"LLM call failed: {e}") from e