"""Drop-in middleware decorator for transparent TokReducer compression."""

from __future__ import annotations

import functools
from typing import Callable

from tokreducer.compressor import TokReducer, Level


def middleware(
    level: int | Level = Level.MEDIUM,
    bidirectional: bool = False,
) -> Callable:
    """Decorator that wraps an ``(prompt: str) -> str`` function.

    The prompt is compressed before the wrapped function is called.
    If *bidirectional* is True the response is decompressed afterwards.

    Usage::

        @middleware(level=2, bidirectional=True)
        def ask_llm(prompt: str) -> str:
            return call_your_llm_api(prompt)

        answer = ask_llm("Write a comprehensive analysis of climate policy")
        # answer is FULL — not shortened
    """
    tok = TokReducer(level=level, bidirectional=bidirectional)

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        @functools.wraps(fn)
        def wrapper(prompt: str, *args, **kwargs) -> str:  # noqa: ANN002,ANN003
            compressed = tok.compress(prompt)
            result = fn(compressed, *args, **kwargs)
            if bidirectional and isinstance(result, str):
                result = tok.decompress(result)
            return result

        wrapper.tokreducer = tok  # type: ignore[attr-defined]
        return wrapper

    return decorator
