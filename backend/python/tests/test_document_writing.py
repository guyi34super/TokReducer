"""Integration tests — document writing with compressed prompts.

Requires a live LLM API key (OPENAI_API_KEY).
"""

import pytest

from tokreducer import TokReducer, Level
from tokreducer.testing import LLMTestClient

pytestmark = pytest.mark.integration


class TestDocumentWriting:
    def test_business_plan_completeness(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            "[TOKREDUCER:1.0 tok:2] @expert:business "
            "> business-plan ctx:saas-startup "
            "sections:executive+market+product+financial+roadmap"
        )
        output = client.ask(compressed, system=tok.system_prompt())

        required_sections = ["executive", "market", "financial", "roadmap"]
        for section in required_sections:
            assert section in output.lower(), (
                f"Missing section: {section} — output may have been truncated"
            )

    def test_email_draft_tone_preserved(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            "[TOKREDUCER:1.0 tok:2] @expert:copywriting "
            "> email ctx:client-followup tone=professional+warm "
            "goal:schedule-demo !jargon"
        )
        output = client.ask(compressed, system=tok.system_prompt())
        assert "subject" in output.lower() or "dear" in output.lower()
        assert len(output.split()) >= 80

    def test_technical_doc_has_code_examples(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            "[TOKREDUCER:1.0 tok:2] @expert:software-docs "
            "> technical-doc ctx:rest-api-auth "
            "sections:overview+endpoints+examples+errors "
            "eg:curl+python !marketing-language"
        )
        output = client.ask(compressed, system=tok.system_prompt())
        assert "curl" in output.lower() or "```" in output
        assert len(output.split()) >= 300

    def test_report_word_count_not_reduced(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        verbose = "Write a comprehensive 500-word report on climate change impacts."
        compressed = tok.compress(verbose)

        out_verbose = client.ask(verbose)
        out_compressed = client.ask(compressed, system=tok.system_prompt())

        words_v = len(out_verbose.split())
        words_c = len(out_compressed.split())
        assert abs(words_v - words_c) / words_v < 0.20, (
            f"Verbose: {words_v} words, Compressed: {words_c} words — mirroring!"
        )
