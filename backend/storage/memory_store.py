import asyncio
import logging
from collections import OrderedDict
from copy import deepcopy
from time import monotonic
from typing import Any
from uuid import uuid4


class ImageNotFoundError(Exception):
    pass


class StepOrderError(Exception):
    pass


logger = logging.getLogger("satellite-backend")


class MemoryStore:
    """In-memory store for user-driven step pipeline state."""

    def __init__(self, max_items: int = 100, ttl_seconds: int = 3600) -> None:
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_items = max(1, max_items)
        self._ttl_seconds = max(60, ttl_seconds)

    def _cleanup_expired_locked(self) -> None:
        now = monotonic()
        expired_ids = [
            image_id
            for image_id, entry in self._store.items()
            if entry.get("expires_at", 0.0) <= now
        ]
        for image_id in expired_ids:
            self._store.pop(image_id, None)
            logger.info("Memory store TTL eviction: image_id=%s", image_id)

    def _evict_if_oversized_locked(self) -> None:
        while len(self._store) >= self._max_items:
            evicted_id, _ = self._store.popitem(last=False)
            logger.warning("Memory store LRU eviction: image_id=%s max_items=%d", evicted_id, self._max_items)

    def _get_entry_locked(self, image_id: str) -> dict[str, Any]:
        entry = self._store.get(image_id)
        if not entry:
            raise ImageNotFoundError("Invalid image_id")

        now = monotonic()
        if entry.get("expires_at", 0.0) <= now:
            self._store.pop(image_id, None)
            logger.info("Memory store expired entry access rejected: image_id=%s", image_id)
            raise ImageNotFoundError("Invalid image_id")

        entry["last_accessed_at"] = now
        entry["expires_at"] = now + self._ttl_seconds
        self._store.move_to_end(image_id)
        return entry

    async def create_entry(self, image_bytes: bytes, step1: dict[str, Any]) -> str:
        image_id = str(uuid4())
        async with self._lock:
            self._cleanup_expired_locked()
            self._evict_if_oversized_locked()
            now = monotonic()
            self._store[image_id] = {
                "image_bytes": bytes(image_bytes),
                "step1": deepcopy(step1),
                "step2": None,
                "created_at": now,
                "last_accessed_at": now,
                "expires_at": now + self._ttl_seconds,
            }
            self._store.move_to_end(image_id)
        return image_id

    async def get_step1(self, image_id: str) -> dict[str, Any]:
        async with self._lock:
            self._cleanup_expired_locked()
            entry = self._get_entry_locked(image_id)
            step1 = entry.get("step1")
            if not isinstance(step1, dict):
                raise StepOrderError("Step 1 result is missing for this image_id")
            return deepcopy(step1)

    async def save_step2(self, image_id: str, step2: dict[str, Any]) -> None:
        async with self._lock:
            self._cleanup_expired_locked()
            entry = self._get_entry_locked(image_id)
            step1 = entry.get("step1")
            if not isinstance(step1, dict):
                raise StepOrderError("Step 1 must be completed before Step 2")
            entry["step2"] = deepcopy(step2)

    async def get_for_generation(self, image_id: str) -> tuple[bytes, list[str]]:
        async with self._lock:
            self._cleanup_expired_locked()
            entry = self._get_entry_locked(image_id)

            step2 = entry.get("step2")
            if not isinstance(step2, dict):
                raise StepOrderError("Step 2 must be completed before Step 3")

            improvements = step2.get("improvements")
            if not isinstance(improvements, list) or not improvements:
                raise StepOrderError("Step 2 improvements are missing for this image_id")

            image_bytes = entry.get("image_bytes")
            if not isinstance(image_bytes, (bytes, bytearray)):
                raise StepOrderError("Stored image is missing for this image_id")

            return bytes(image_bytes), [str(item) for item in improvements]


memory_store = MemoryStore()
