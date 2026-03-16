"""Integration tests — verify compressed prompts produce full-quality output.

Requires a live LLM API key (OPENAI_API_KEY).
"""

import pytest

from tokreducer import TokReducer, Level
from tokreducer.testing import LLMTestClient, compare_outputs

pytestmark = pytest.mark.integration


class TestOutputCompleteness:
    def test_verbose_vs_compressed_output_length(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)

        verbose = (
            "You are an expert historian. Please provide a "
            "comprehensive explanation of the causes of World War I, "
            "covering political, economic, and social factors in detail."
        )
        compressed = tok.compress(verbose)

        out_verbose = client.ask(verbose)
        out_compressed = client.ask(compressed, system=tok.system_prompt())

        ratio = len(out_compressed) / len(out_verbose)
        assert 0.85 <= ratio <= 1.15, (
            f"Output length ratio {ratio:.2f} — possible mirroring detected!"
        )

    def test_output_contains_required_sections(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = tok.compress(
            "@expert:history explain:WW1-causes >> political+economic+social"
        )
        output = client.ask(compressed, system=tok.system_prompt())

        assert "political" in output.lower()
        assert "economic" in output.lower()
        assert "social" in output.lower()

    def test_compare_outputs_within_tolerance(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)

        verbose = "Explain the water cycle in detail, covering evaporation, condensation, and precipitation."
        compressed = tok.compress(verbose)

        out_v = client.ask(verbose)
        out_c = client.ask(compressed, system=tok.system_prompt())

        report = compare_outputs(out_v, out_c, tolerance=0.20)
        assert report["within_tolerance"], (
            f"Word-count ratio {report['ratio']} outside 20% tolerance"
        )

    def test_compressed_output_not_empty(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = tok.compress(
            "Write a paragraph about the importance of renewable energy."
        )
        output = client.ask(compressed, system=tok.system_prompt())
        assert len(output.split()) >= 50, "Output too short — may be truncated"
