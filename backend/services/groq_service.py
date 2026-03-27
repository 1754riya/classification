import json
import logging
import os
from asyncio import Lock, sleep
from typing import Any

import httpx
from dotenv import load_dotenv

from services.errors import UpstreamTimeoutError

load_dotenv()

logger = logging.getLogger("satellite-backend")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

_groq_client: httpx.AsyncClient | None = None
_groq_init_lock = Lock()


class GroqServiceError(Exception):
    pass


async def get_groq_client() -> httpx.AsyncClient:
    global _groq_client
    if _groq_client is not None:
        return _groq_client

    async with _groq_init_lock:
        if _groq_client is None:
            _groq_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
            logger.info("Initialized shared Groq AsyncClient")

    return _groq_client


async def close_groq_client() -> None:
    global _groq_client
    if _groq_client is not None:
        await _groq_client.aclose()
        _groq_client = None
        logger.info("Closed shared Groq AsyncClient")


def _safe_json_loads(value: str) -> dict[str, Any]:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        cleaned = value.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GroqServiceError(f"Invalid JSON returned from Groq: {exc}") from exc


def _extract_retry_after_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if not retry_after:
        return None
    try:
        return max(0.0, float(retry_after))
    except ValueError:
        return None


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or status_code in {500, 502, 503, 504}


async def _call_groq_chat_completion(payload: dict[str, Any]) -> dict[str, Any]:
    if not GROQ_API_KEY:
        logger.error("Groq API key not configured")
        raise GroqServiceError("GROQ_API_KEY is not configured")

    url = f"{GROQ_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    client = await get_groq_client()

    max_attempts = 4
    backoff_seconds = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.error("Groq request timed out (model=%s)", GROQ_MODEL)
            raise UpstreamTimeoutError(f"Groq timeout for model {GROQ_MODEL}") from exc
        except httpx.HTTPError as exc:
            logger.error("Groq HTTP error (model=%s error=%s)", GROQ_MODEL, str(exc))
            raise GroqServiceError(f"Groq HTTP error for model {GROQ_MODEL}: {exc}") from exc

        if response.status_code < 400:
            return response.json()

        if _is_retryable_status(response.status_code) and attempt < max_attempts:
            retry_after = _extract_retry_after_seconds(response)
            wait_seconds = retry_after if retry_after is not None else backoff_seconds
            logger.warning(
                "Groq retryable failure (status=%d model=%s attempt=%d/%d wait=%.2fs)",
                response.status_code,
                GROQ_MODEL,
                attempt,
                max_attempts,
                wait_seconds,
            )
            await sleep(wait_seconds)
            backoff_seconds = min(backoff_seconds * 2, 8.0)
            continue

        logger.error(
            "Groq request failed (status=%d model=%s): %s",
            response.status_code,
            GROQ_MODEL,
            response.text,
        )
        raise GroqServiceError(
            f"Groq request failed ({response.status_code}): {response.text}"
        )

    raise GroqServiceError("Groq request failed after retries")


async def get_improvements(step1_json: dict[str, Any]) -> dict[str, list[str]]:
    prompt = (
        "Given the satellite analysis JSON below, provide practical suggestions to make the area "
        "more sustainable, eco-friendly, and visually appealing. Return strict JSON in this shape: "
        '{"improvements": ["...", "..."]}.\n\n'
        f"Analysis JSON:\n{json.dumps(step1_json)}"
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an urban planning assistant. Always return valid JSON only, "
                    "with no markdown fences and no extra keys."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
    }

    response_json = await _call_groq_chat_completion(payload)
    choices = response_json.get("choices", [])
    if not choices:
        raise GroqServiceError("No Groq choices returned")

    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise GroqServiceError("Groq response content is empty")

    parsed = _safe_json_loads(content)
    if not isinstance(parsed, dict):
        raise GroqServiceError("Groq response must be a JSON object")

    improvements = parsed.get("improvements")
    if not isinstance(improvements, list):
        raise GroqServiceError("Groq response must contain list 'improvements'")

    cleaned = [str(item).strip() for item in improvements if str(item).strip()]
    if not cleaned:
        raise GroqServiceError("Groq response returned empty improvements list")

    return {"improvements": cleaned}
