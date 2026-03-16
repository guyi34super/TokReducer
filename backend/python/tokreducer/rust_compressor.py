"""Rust compressor adapter — calls the Rust HTTP service for compress/decompress."""

from __future__ import annotations

from tokreducer.compressor import Level
from tokreducer.system_prompt import get_system_prompt

import httpx


class RustCompressor:
    """Compressor that delegates to the Rust HTTP service.

    Implements the same interface as TokReducer for drop-in replacement.
    """

    def __init__(
        self,
        level: Level | int,
        bidirectional: bool = False,
        base_url: str = "",
    ) -> None:
        self.level = Level(level)
        self.bidirectional = bidirectional
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    def compress(self, raw: str) -> str:
        resp = self._client.post(
            f"{self._base}/compress",
            json={"prompt": raw, "level": int(self.level)},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["compressed"]

    def decompress(self, text: str) -> str:
        resp = self._client.post(
            f"{self._base}/decompress",
            json={"text": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["decompressed"]

    def count(self, text: str) -> int:
        resp = self._client.post(
            f"{self._base}/count",
            json={"text": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["tokens"]

    def reduction_pct(self, raw: str, compressed: str) -> float:
        resp = self._client.post(
            f"{self._base}/reduction_pct",
            json={
                "raw": raw,
                "compressed": compressed,
                "level": int(self.level),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["reduction_pct"]

    def system_prompt(self) -> str:
        return get_system_prompt()
