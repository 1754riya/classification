import json
import logging
import math
import os
from asyncio import Lock, sleep
from typing import Any

import httpx
from dotenv import load_dotenv

from services.errors import UpstreamTimeoutError
from utils.image_utils import encode_bytes_to_base64, image_bytes_to_png_bytes

load_dotenv()

logger = logging.getLogger("satellite-backend")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_VISION_KEY = os.getenv("GEMINI_VISION_KEY", "")
GEMINI_IMAGE_KEY = os.getenv("GEMINI_IMAGE_KEY", "")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-3-flash-preview")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash")

# ISSUE 5 FIX: Shared AsyncClient to avoid creating new client for each request
_gemini_client: httpx.AsyncClient | None = None
_gemini_lock = Lock()


async def get_gemini_client() -> httpx.AsyncClient:
    """Get or create the shared Gemini HTTP client."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    return _gemini_client


async def close_gemini_client() -> None:
    """Close the shared Gemini HTTP client."""
    global _gemini_client
    if _gemini_client is not None:
        await _gemini_client.aclose()
        _gemini_client = None


class GeminiServiceError(Exception):
    pass


def _validate_feature_coordinates(feature: dict[str, Any], index: int) -> None:
    coordinates = feature.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 4:
        logger.error("Invalid coordinates shape for feature index=%d", index)
        raise GeminiServiceError("Feature 'coordinates' must be [x, y, width, height]")

    for coordinate in coordinates:
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            logger.error("Invalid coordinate type for feature index=%d type=%s", index, type(coordinate).__name__)
            raise GeminiServiceError("Feature coordinates must be int or float values")
        if not math.isfinite(float(coordinate)):
            logger.error("Non-finite coordinate for feature index=%d", index)
            raise GeminiServiceError("Feature coordinates must be finite numeric values")


def _extract_first_text(response_json: dict[str, Any]) -> str:
    candidates = response_json.get("candidates", [])
    if not candidates:
        raise GeminiServiceError("No Gemini candidates returned")

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    for part in parts:
        text = part.get("text")
        if text:
            return text

    raise GeminiServiceError("Gemini text content was empty")


def _extract_first_image_base64(response_json: dict[str, Any]) -> str:
    candidates = response_json.get("candidates", [])
    if not candidates:
        raise GeminiServiceError("No Gemini candidates returned")

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    for part in parts:
        inline_data = part.get("inlineData")
        if inline_data and inline_data.get("data"):
            return inline_data["data"]

    raise GeminiServiceError("Gemini image data was not found in response")


def _safe_json_loads(value: str) -> dict[str, Any]:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        # Gemini may return fenced JSON. Strip code fences if present.
        cleaned = value.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GeminiServiceError(f"Invalid JSON returned from Gemini: {exc}") from exc


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


def _resolve_shared_gemini_key() -> str:
    """Resolve one shared Gemini key for both Step 1 and Step 3.

    Priority:
    1) GEMINI_API_KEY
    2) GEMINI_VISION_KEY / GEMINI_IMAGE_KEY if present and equal
    3) Either legacy key if only one is present
    """
    if GEMINI_API_KEY:
        return GEMINI_API_KEY

    if GEMINI_VISION_KEY and GEMINI_IMAGE_KEY:
        if GEMINI_VISION_KEY != GEMINI_IMAGE_KEY:
            raise GeminiServiceError(
                "GEMINI_VISION_KEY and GEMINI_IMAGE_KEY must match (single key required)"
            )
        return GEMINI_VISION_KEY

    if GEMINI_VISION_KEY:
        return GEMINI_VISION_KEY

    if GEMINI_IMAGE_KEY:
        return GEMINI_IMAGE_KEY

    raise GeminiServiceError(
        "Gemini API key is not configured (set GEMINI_API_KEY or matching GEMINI_VISION_KEY/GEMINI_IMAGE_KEY)"
    )


async def _call_generate_content(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Call Gemini API with retry support for rate limiting and transient failures."""
    api_key = _resolve_shared_gemini_key()

    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    params = {"key": api_key}
    client = await get_gemini_client()

    async with _gemini_lock:
        max_attempts = 4
        backoff_seconds = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(url, params=params, json=payload)
            except httpx.TimeoutException as exc:
                logger.error("Gemini request timed out (model=%s)", model)
                raise UpstreamTimeoutError(f"Gemini timeout for model {model}") from exc
            except httpx.HTTPError as exc:
                logger.error("Gemini HTTP error (model=%s error=%s)", model, str(exc))
                raise GeminiServiceError(f"Gemini HTTP error for model {model}: {exc}") from exc

            if response.status_code < 400:
                return response.json()

            if _is_retryable_status(response.status_code) and attempt < max_attempts:
                retry_after = _extract_retry_after_seconds(response)
                wait_seconds = retry_after if retry_after is not None else backoff_seconds
                logger.warning(
                    "Gemini retryable failure (status=%d model=%s attempt=%d/%d wait=%.2fs)",
                    response.status_code,
                    model,
                    attempt,
                    max_attempts,
                    wait_seconds,
                )
                await sleep(wait_seconds)
                backoff_seconds = min(backoff_seconds * 2, 8.0)
                continue

            logger.error(
                "Gemini request failed (status=%d model=%s): %s",
                response.status_code,
                model,
                response.text,
            )
            raise GeminiServiceError(
                f"Gemini request failed ({response.status_code}): {response.text}"
            )

    raise GeminiServiceError("Gemini request failed after retries")


async def analyze_image(image_bytes: bytes) -> dict[str, Any]:
    image_b64 = encode_bytes_to_base64(image_bytes_to_png_bytes(image_bytes))
    prompt = (
        "Analyze this satellite image. Return strict JSON with this exact shape: "
        "{\"classification\": string, \"features\": [{\"name\": string, "
        "\"coordinates\": [x, y, width, height]}], \"description\": string}. "
        "The coordinates must be numeric values and features must be an array of objects."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": image_b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    response_json = await _call_generate_content(GEMINI_VISION_MODEL, payload)
    parsed = _safe_json_loads(_extract_first_text(response_json))

    missing = [k for k in ["classification", "features", "description"] if k not in parsed]
    if missing:
        raise GeminiServiceError(f"Gemini analysis response missing keys: {missing}")

    if not isinstance(parsed.get("features"), list):
        raise GeminiServiceError("Gemini analysis response has invalid 'features' type")

    for index, feature in enumerate(parsed["features"]):
        if not isinstance(feature, dict):
            raise GeminiServiceError("Each feature must be an object")
        if "name" not in feature or "coordinates" not in feature:
            raise GeminiServiceError("Each feature must include 'name' and 'coordinates'")
        _validate_feature_coordinates(feature, index)

    return parsed


async def generate_image(image_bytes: bytes, improvements: list[str]) -> str:
    image_b64 = encode_bytes_to_base64(image_bytes_to_png_bytes(image_bytes))
    improvements_text = "; ".join(improvements)

    prompt = (
        "Generate an improved satellite image with these enhancements: "
        f"{improvements_text}. Keep geography realistic and preserve main structures."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": image_b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "temperature": 0.4,
        },
    }

    response_json = await _call_generate_content(GEMINI_IMAGE_MODEL, payload)
    return _extract_first_image_base64(response_json)
