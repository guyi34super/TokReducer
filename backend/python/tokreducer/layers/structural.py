"""Layer 2 — Structural Compression.

Replaces verbose prompt scaffolding with bracket notation and operators.
Applied at tok:2+.
"""

from __future__ import annotations

import re

_MACROS: dict[str, str] = {
    "[TASK]": "The task I need you to complete is:",
    "[CONTEXT]": "Here is the relevant background context:",
    "[RULES]": "Follow these rules strictly:",
    "[FORMAT]": "The output format should be:",
    "[EXAMPLE]": "Here is an example input/output pair:",
    "[DATA]": "Here is the data to process:",
    "[GOAL]": "The end goal of this task is:",
    "[CONSTRAINTS]": "You must stay within these constraints:",
}

_STRUCTURAL_PATTERNS: list[tuple[str, str]] = [
    ("the task i need you to complete is:", "[TASK]"),
    ("the task i need you to complete is", "[TASK]"),
    ("here is the relevant background context:", "[CONTEXT]"),
    ("here is the relevant background context", "[CONTEXT]"),
    ("follow these rules strictly:", "[RULES]"),
    ("follow these rules strictly", "[RULES]"),
    ("the output format should be:", "[FORMAT]"),
    ("the output format should be", "[FORMAT]"),
    ("here is an example input/output pair:", "[EXAMPLE]"),
    ("here is an example input/output pair", "[EXAMPLE]"),
    ("here is the data to process:", "[DATA]"),
    ("here is the data to process", "[DATA]"),
    ("the end goal of this task is:", "[GOAL]"),
    ("the end goal of this task is", "[GOAL]"),
    ("you must stay within these constraints:", "[CONSTRAINTS]"),
    ("you must stay within these constraints", "[CONSTRAINTS]"),
]

_COMPRESS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(re.escape(phrase), re.IGNORECASE), macro)
    for phrase, macro in _STRUCTURAL_PATTERNS
]

_FILLER = re.compile(
    r"\b(?:the|a|an|of|for|is|it|its|this|that|these|those|"
    r"with|from|into|about|between|through|during|"
    r"very|really|just|also|then|so|but|"
    r"could you|can you|would you|"
    r"i need you to|i want you to|i would like you to|"
    r"make sure to|be sure to|ensure that|"
    r"please note that|note that|keep in mind that|"
    r"it is important to|it's important to|"
    r"here is|here are)\b",
    re.IGNORECASE,
)

_CONJUNCTION = re.compile(
    r"\s*,?\s*(?:and|as well as|along with|together with|in addition to)\s+",
    re.IGNORECASE,
)

# When "ctx:code-review" is present, the specific issue types are redundant.
_REDUNDANT_AFTER_CODE_REVIEW = re.compile(
    r"(ctx:code-review)\s*(?:>>)?\s*(?:bugs?\+?|security\+?|perf\+?|style\+?|issues?\+?)*",
    re.IGNORECASE,
)


class StructuralCompressor:
    """Layer 2: replace verbose scaffolding with bracket notation / operators."""

    def compress(self, text: str) -> str:
        result = text

        for pattern, macro in _COMPRESS_PATTERNS:
            result = pattern.sub(macro, result)

        result = _CONJUNCTION.sub("+", result)
        result = _FILLER.sub("", result)

        # Comma-separated items -> "+"
        result = re.sub(r"\s*,\s*", "+", result)

        # Absorb redundant issue types after ctx:code-review.
        result = _REDUNDANT_AFTER_CODE_REVIEW.sub(r"\1 >>", result)

        # Clean up.
        result = re.sub(r"\+\+", "+", result)
        result = re.sub(r"\s+\+", "+", result)
        result = re.sub(r"\+\s+", "+", result)
        result = re.sub(r"\.+\s*", " ", result)
        result = re.sub(r">> >>", ">>", result)
        result = re.sub(r"  +", " ", result).strip()

        return result

    def decompress(self, text: str) -> str:
        result = text
        for macro, expansion in _MACROS.items():
            result = result.replace(macro, expansion)

        def _expand_role(m: re.Match[str]) -> str:
            role = m.group(1).replace("-", " ")
            return f"You are an expert {role}"

        result = re.sub(r"@expert:([\w-]+)", _expand_role, result)
        result = re.sub(r"ctx:([\w-]+)", r"in the context of \1", result)
        return result
