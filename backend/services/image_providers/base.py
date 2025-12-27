from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageProvider(Protocol):
    name: str

    async def generate(
        self, prompt: str, *, size: str | None = None, quality: str | None = None, n: int = 1
    ) -> list[bytes]:
        """Generate ``n`` images as raw bytes."""
        ...
