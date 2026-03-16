"""Integration tests — code review with compressed prompts.

Requires a live LLM API key (OPENAI_API_KEY).
"""

import pytest

from tokreducer import TokReducer, Level
from tokreducer.testing import LLMTestClient

pytestmark = pytest.mark.integration

SAMPLE_CODE = '''
def get_user(id):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM users WHERE id = {id}')
    return cursor.fetchone()
'''


class TestCodeReview:
    def test_compression_reduces_tokens(self):
        tok = TokReducer(level=Level.MEDIUM)
        verbose = (
            "You are a senior Python engineer with 10 years of experience. "
            "Please carefully review the following Python code. "
            "Identify all bugs, security vulnerabilities, performance issues, "
            "and style problems. For each issue found, explain what the problem "
            "is and provide a corrected version of the code. "
            "Format your response as a numbered list."
        )
        compressed = tok.compress(verbose)
        reduction = tok.reduction_pct(verbose, compressed)
        assert reduction >= 65, f"Expected >=65% reduction, got {reduction:.1f}%"

    def test_compressed_review_finds_sql_injection(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            f"[TOKREDUCER:1.0 tok:2] @expert:python+security "
            f"ctx:code-review >> •list bugs+security+perf\n{SAMPLE_CODE}"
        )
        output = client.ask(compressed, system=tok.system_prompt())
        assert "sql injection" in output.lower() or "injection" in output.lower()

    def test_compressed_review_finds_missing_close(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            f"[TOKREDUCER:1.0 tok:2] @expert:python "
            f"ctx:code-review >> •list\n{SAMPLE_CODE}"
        )
        output = client.ask(compressed, system=tok.system_prompt())
        assert "close" in output.lower() or "connection" in output.lower()

    def test_code_review_output_includes_fix(self, client: LLMTestClient):
        tok = TokReducer(level=Level.MEDIUM)
        compressed = (
            f"[TOKREDUCER:1.0 tok:2] @expert:python "
            f"ctx:code-review >> •list+fixes\n{SAMPLE_CODE}"
        )
        output = client.ask(compressed, system=tok.system_prompt())
        assert "def get_user" in output or "parameterized" in output.lower()
