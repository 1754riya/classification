from typing import Any
from uuid import uuid4

_sessions: dict[str, dict[str, Any]] = {}


class SessionNotFound(Exception):
    pass


class StepRequired(Exception):
    pass


def create_session(image_bytes: bytes, analysis: dict[str, Any]) -> str:
    sid = str(uuid4())
    _sessions[sid] = {
        "image": bytes(image_bytes),
        "analysis": analysis,
        "suggestions": None,
    }
    return sid


def get_analysis(sid: str) -> dict[str, Any]:
    if sid not in _sessions:
        raise SessionNotFound(sid)
    return _sessions[sid]["analysis"]


def save_suggestions(sid: str, suggestions: list[str]) -> None:
    if sid not in _sessions:
        raise SessionNotFound(sid)
    _sessions[sid]["suggestions"] = suggestions


def get_for_generation(sid: str) -> tuple[bytes, list[str]]:
    if sid not in _sessions:
        raise SessionNotFound(sid)
    suggestions = _sessions[sid].get("suggestions")
    if not suggestions:
        raise StepRequired("Complete /suggest before /imagine")
    return _sessions[sid]["image"], suggestions
