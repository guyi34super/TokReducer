"""Integration tests — data analysis with compressed prompts.

Requires a live LLM API key (OPENAI_API_KEY).
"""

import json

import pytest

from tokreducer import TokReducer, Level
from tokreducer.testing import LLMTestClient

pytestmark = pytest.mark.integration

SAMPLE_CSV = """month,revenue,users,churn_rate
Jan,12000,450,0.05
Feb,13500,480,0.04
Mar,11000,460,0.07
Apr,15000,520,0.03"""


class TestDataAnalysis:
    def test_json_output_format_respected(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            f"[TOKREDUCER:1.0 tok:2] @expert:data-analysis "
            f"[DATA] analyze:trends+anomalies recommend:3 fmt:json\n{SAMPLE_CSV}"
        )
        output = client.ask(compressed, system=tok.system_prompt())

        cleaned = output.strip().strip("`").replace("json", "", 1).strip()
        try:
            parsed = json.loads(cleaned)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON — format instruction ignored")

    def test_all_requested_metrics_present(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            f"[TOKREDUCER:1.0 tok:2] @expert:data-analysis "
            f"[DATA] analyze:revenue+users+churn >> •list\n{SAMPLE_CSV}"
        )
        output = client.ask(compressed, system=tok.system_prompt())

        assert "revenue" in output.lower()
        assert "user" in output.lower()
        assert "churn" in output.lower()

    def test_anomaly_detected_march_churn(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            f"[TOKREDUCER:1.0 tok:2] @expert:data "
            f"[DATA] identify:anomalies\n{SAMPLE_CSV}"
        )
        output = client.ask(compressed, system=tok.system_prompt())

        assert "march" in output.lower() or "mar" in output.lower()
        assert "churn" in output.lower()
