"""Unit tests for the compression engine — no API key required."""

import pytest

from tokreducer import TokReducer, Level
from tokreducer.tokenizer import count_tokens


class TestCompressionRates:
    def test_lexical_compression_level1(self):
        tok = TokReducer(level=Level.LIGHT)
        raw = (
            "Please write a detailed summary of the following text. "
            "Please provide a comprehensive explanation of the key themes. "
            "Include bullet points for the main ideas."
        )
        compressed = tok.compress(raw)
        reduction = tok.reduction_pct(raw, compressed)
        assert reduction >= 30, f"Expected >=30% reduction, got {reduction:.1f}%"

    def test_structural_compression_level2(self):
        tok = TokReducer(level=Level.MEDIUM)
        raw = (
            "You are an expert software engineer. "
            "Please carefully review the following code for "
            "bugs, performance issues, and style problems. "
            "For each issue found, explain what the problem is "
            "and provide a corrected version of the code. "
            "Format your response as a numbered list."
        )
        compressed = tok.compress(raw)
        reduction = tok.reduction_pct(raw, compressed)
        assert reduction >= 60, f"Expected >=60% reduction, got {reduction:.1f}%"

    def test_semantic_compression_level3(self):
        tok = TokReducer(level=Level.MAX)
        raw = (
            "You are a world-class oncologist. Please provide a comprehensive, "
            "detailed explanation of how chemotherapy works, covering the "
            "mechanism of action, main drug classes, side effects, and how "
            "treatment protocols are designed for different cancer types. "
            "For each drug class, explain the mechanism of action in detail "
            "and provide real-world examples of commonly used medications. "
            "Also include a section on emerging therapies and immunotherapy "
            "approaches that are currently in clinical trials."
        )
        compressed = tok.compress(raw)
        reduction = tok.reduction_pct(raw, compressed)
        assert reduction >= 80, f"Expected >=80% reduction, got {reduction:.1f}%"

    def test_activation_header_present(self):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = tok.compress("Summarize this document")
        assert "[TOKREDUCER:1.0" in compressed

    def test_short_prompt_skip_threshold(self):
        tok = TokReducer(level=Level.MEDIUM, skip_below_tokens=20)
        short = "What is 2 + 2?"
        result = tok.compress(short)
        assert result == short

    def test_system_prompt_contains_output_rule(self):
        tok = TokReducer(level=Level.MEDIUM)
        sp = tok.system_prompt()
        assert "CRITICAL OUTPUT RULE" in sp
        assert "full" in sp.lower() or "compressed input" in sp.lower()
