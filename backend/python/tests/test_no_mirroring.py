"""Integration tests — verify short input does NOT produce short output.

These are the most critical behavioral tests in TokReducer.
Requires a live LLM API key (OPENAI_API_KEY).
"""

import pytest

from tokreducer import TokReducer, Level
from tokreducer.testing import LLMTestClient

pytestmark = pytest.mark.integration


class TestNoLengthMirroring:
    """Confirm Theory 3: a short compressed prompt does NOT cause
    the LLM to produce a shorter answer."""

    def test_8_token_prompt_produces_full_explanation(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MAX)
        compressed = "[TOKREDUCER:1.0 tok:3] explain:transformer-architecture"
        output = client.ask(compressed, system=tok.system_prompt())

        assert len(output.split()) >= 300, (
            f"Only {len(output.split())} words — likely mirroring short input!"
        )

    def test_mirroring_without_system_prompt_detected(self, client: LLMTestClient):
        """Confirm the problem exists WITHOUT TokReducer system prompt."""
        compressed = "[TOKREDUCER:1.0 tok:3] explain:transformer-architecture"

        output_no_sp = client.ask(compressed, system=None)
        tok = TokReducer(level=Level.MAX)
        output_with_sp = client.ask(compressed, system=tok.system_prompt())

        words_no_sp = len(output_no_sp.split())
        words_with_sp = len(output_with_sp.split())

        assert words_with_sp > words_no_sp, (
            "System prompt had no effect on output length"
        )

    def test_max_compression_same_output_as_verbose(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MAX)
        verbose = (
            "You are a world-class oncologist. Please provide a comprehensive, "
            "detailed explanation of how chemotherapy works, covering the "
            "mechanism of action, main drug classes, side effects, and how "
            "treatment protocols are designed for different cancer types."
        )
        compressed = tok.compress(verbose)

        out_verbose = client.ask(verbose)
        out_compressed = client.ask(compressed, system=tok.system_prompt())

        ratio = len(out_compressed.split()) / len(out_verbose.split())
        assert 0.80 <= ratio <= 1.20, (
            f"Output ratio {ratio:.2f}. tok:3 compressed input "
            f"produced significantly different output length."
        )

    def test_no_mirroring_code_generation(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MAX)
        compressed = (
            "[TOKREDUCER:1.0 tok:3] @expert:python "
            "> REST-API lang:fastapi+sqlalchemy "
            "endpoints:users+auth+products full-implementation"
        )
        output = client.ask(compressed, system=tok.system_prompt())

        assert output.count("def ") >= 5, "Too few functions — truncated"
        assert output.count("async") >= 3, "Missing async handlers"
        assert "import" in output, "Missing imports — incomplete"
