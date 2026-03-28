import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash")

_client = httpx.AsyncClient(timeout=60.0)


class GeminiError(Exception):
    pass


async def close() -> None:
    await _client.aclose()


async def _post(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not configured")
    url = f"{GEMINI_BASE}/{model}:generateContent"
    resp = await _client.post(url, params={"key": GEMINI_API_KEY}, json=payload)
    if resp.status_code >= 400:
        raise GeminiError(f"Gemini error {resp.status_code}: {resp.text}")
    return resp.json()


def _first_text(response: dict[str, Any]) -> str:
    try:
        for part in response["candidates"][0]["content"]["parts"]:
            if "text" in part:
                return part["text"]
    except (KeyError, IndexError):
        pass
    raise GeminiError("No text in Gemini response")


def _first_image(response: dict[str, Any]) -> str:
    try:
        for part in response["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                return part["inlineData"]["data"]
    except (KeyError, IndexError):
        pass
    raise GeminiError("No image in Gemini response")


def _parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = text.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GeminiError(f"Invalid JSON from Gemini: {exc}") from exc


async def analyze(image_b64: str) -> dict[str, Any]:
    prompt = (
        "Analyze this satellite image. Return JSON with exactly these keys: "
        '{"classification": string, "objects": [string, ...], "description": string}. '
        "classification is the land-use type; objects is a list of detected features."
    )
    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": "image/png", "data": image_b64}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    result = _parse_json(_first_text(await _post(VISION_MODEL, payload)))
    for key in ("classification", "objects", "description"):
        if key not in result:
            raise GeminiError(f"Missing key in Gemini response: {key}")
    if not isinstance(result["objects"], list):
        raise GeminiError("'objects' must be a list")
    return result


async def generate(image_b64: str, suggestions: list[str]) -> str:
    prompt = (
        "Generate an improved satellite image applying these urban planning suggestions: "
        + "; ".join(suggestions)
        + ". Keep the geography realistic and preserve main structures."
    )
    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": "image/png", "data": image_b64}},
        ]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"], "temperature": 0.4},
    }
    return _first_image(await _post(IMAGE_MODEL, payload))
