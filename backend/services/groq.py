import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-4-scout-17b-16e-instruct")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_client = httpx.AsyncClient(timeout=60.0)


class GroqError(Exception):
    pass


async def close() -> None:
    await _client.aclose()


async def get_suggestions(analysis: dict[str, Any]) -> list[str]:
    if not GROQ_API_KEY:
        raise GroqError("GROQ_API_KEY is not configured")

    prompt = (
        "Given this satellite image analysis, suggest practical urban planning improvements "
        "to make the area more sustainable and livable. Return JSON: "
        '{"suggestions": ["...", "..."]}.\n\nAnalysis: '
        + json.dumps(analysis)
    )
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are an urban planning expert. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
    }

    resp = await _client.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json=payload,
    )
    if resp.status_code >= 400:
        raise GroqError(f"Groq error {resp.status_code}: {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"]
    suggestions = json.loads(content).get("suggestions", [])
    if not isinstance(suggestions, list) or not suggestions:
        raise GroqError("No suggestions returned from Groq")

    return [str(s).strip() for s in suggestions if str(s).strip()]
