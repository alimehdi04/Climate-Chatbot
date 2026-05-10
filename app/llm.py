import ollama
from config import Config


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
    system_prompt = build_system_prompt(passages)

    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": user_message})

    response = ollama.chat(
        model=Config.OLLAMA_MODEL,
        messages=messages,
        options={"temperature": 0.3}
    )

    return response["message"]["content"]