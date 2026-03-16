"""Core TokReducer class — the public API for compression and decompression."""

from __future__ import annotations

from enum import IntEnum

from tokreducer.layers.lexical import LexicalCompressor
from tokreducer.layers.structural import StructuralCompressor
from tokreducer.layers.semantic import SemanticCompressor
from tokreducer.tokenizer import count_tokens
from tokreducer.system_prompt import get_system_prompt


class Level(IntEnum):
    """Compression level matching the tok:N notation."""

    NATURAL = 0  # tok:0 — no compression
    LIGHT = 1    # tok:1 — ~30-50 % reduction (lexical only)
    MEDIUM = 2   # tok:2 — ~60-80 % reduction (lexical + structural)
    MAX = 3      # tok:3 — ~85-95 % reduction (all three layers)


_LEVEL_NAMES = {
    Level.NATURAL: "0",
    Level.LIGHT: "1",
    Level.MEDIUM: "2",
    Level.MAX: "3",
}


class TokReducer:
    """Compress and decompress prompts using the TokReducer 1.0 protocol.

    Parameters
    ----------
    level:
        Compression level (0–3).  Higher = more aggressive.
    bidirectional:
        When *True*, the LLM is also asked to compress its response using
        TokReducer notation, and :meth:`decompress` reverses that encoding.
    skip_below_tokens:
        Prompts shorter than this token count are passed through unchanged
        to avoid overhead on trivially short inputs.
    """

    def __init__(
        self,
        level: Level | int = Level.MEDIUM,
        bidirectional: bool = False,
        skip_below_tokens: int = 0,
    ) -> None:
        self.level = Level(level)
        self.bidirectional = bidirectional
        self.skip_below_tokens = skip_below_tokens

        self._lexical = LexicalCompressor()
        self._structural = StructuralCompressor()
        self._semantic = SemanticCompressor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compress(self, raw: str) -> str:
        """Compress *raw* natural-language prompt into TokReducer notation."""
        if self.level == Level.NATURAL:
            return raw

        if self.skip_below_tokens and count_tokens(raw) < self.skip_below_tokens:
            return raw

        text = raw

        # Layer 1 — Lexical (tok:1+)
        if self.level >= Level.LIGHT:
            text = self._lexical.compress(text)

        # Layer 2 — Structural (tok:2+)
        if self.level >= Level.MEDIUM:
            text = self._structural.compress(text)

        # Layer 3 — Semantic (tok:3 only)
        if self.level >= Level.MAX:
            text = self._semantic.compress(text)

        # Prepend activation header.
        header = f"[TOKREDUCER:1.0 tok:{_LEVEL_NAMES[self.level]}"
        if self.bidirectional:
            header += " respond:tok1.0"
        header += "]"

        return f"{header} {text}"

    def decompress(self, text: str) -> str:
        """Decompress a TokReducer-encoded response back to natural language.

        Decompression is best-effort: Layer 3 (semantic) is inherently lossy
        so only Layers 1 and 2 are reversed.
        """
        result = text

        # Strip the activation header if present.
        if result.startswith("[TOKREDUCER:"):
            bracket_end = result.find("]")
            if bracket_end != -1:
                result = result[bracket_end + 1:].lstrip()

        result = self._structural.decompress(result)
        result = self._lexical.decompress(result)
        return result

    def count(self, text: str) -> int:
        """Return the token count of *text*."""
        return count_tokens(text)

    def reduction_pct(self, raw: str, compressed: str) -> float:
        """Return the percentage of tokens saved by compression.

        The protocol header (``[TOKREDUCER:1.0 tok:N]``) is fixed overhead
        required by the LLM but is not part of the user's *content*.
        This method measures content-level reduction by subtracting the
        header tokens from the compressed count.
        """
        original = count_tokens(raw)
        if original == 0:
            return 0.0
        header_tokens = self._header_token_count()
        reduced = max(count_tokens(compressed) - header_tokens, 1)
        return (1 - reduced / original) * 100

    def _header_token_count(self) -> int:
        """Token count of the activation header alone."""
        header = f"[TOKREDUCER:1.0 tok:{_LEVEL_NAMES[self.level]}"
        if self.bidirectional:
            header += " respond:tok1.0"
        header += "]"
        return count_tokens(header)

    def system_prompt(self) -> str:
        """Return the system prompt that prevents length mirroring."""
        return get_system_prompt()
