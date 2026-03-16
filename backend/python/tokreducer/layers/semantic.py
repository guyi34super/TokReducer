"""Layer 3 — Semantic Compression.

Reduces prompts to semantic anchors — minimal identifiers the LLM expands
using its trained knowledge.  Applied at tok:3 (maximum compression) only.
"""

from __future__ import annotations

import re

_STOP_WORDS = re.compile(
    r"\b(?:the|a|an|of|for|is|it|its|this|that|these|those|"
    r"with|from|into|about|me|my|your|our|how|what|when|where|"
    r"which|who|whom|whose|here|there|"
    r"works?|provides?|gives?|makes?|takes?|gets?|has|have|had|"
    r"should|would|could|will|shall|may|might|must|"
    r"do|does|did|be|been|being|am|are|was|were|"
    r"all|each|every|some|any|no|not|"
    r"on|in|at|to|by|up|out|off|over|under|"
    r"full|or|if|as|and|so|yet|also|"
    r"please|explain|describe|write|create|generate|"
    r"following|main|key|important|relevant|specific|"
    r"include|including|section|detail|detailed|"
    r"commonly|currently|used|using|real-world|"
    r"different|designed|approaches|examples)\b",
    re.IGNORECASE,
)

_OPERATOR_PREFIX = re.compile(r"^[@>#!?~=•]|^(?:ctx:|fmt:|eg:|only>|len[=:]|tok:|\[)")

# Patterns to collapse multi-word phrases into single compact tokens.
_COMPOUND_REDUCTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"mechanism\s+(?:of\s+)?action", re.I), "mechanism"),
    (re.compile(r"drug\s+class(?:es)?", re.I), "drugs"),
    (re.compile(r"side\s+effects?", re.I), "effects"),
    (re.compile(r"treatment\s+protocols?", re.I), "protocols"),
    (re.compile(r"cancer\s+types?", re.I), "cancer"),
    (re.compile(r"clinical\s+trials?", re.I), "trials"),
    (re.compile(r"emerging\s+therap(?:y|ies)", re.I), "emerging-tx"),
    (re.compile(r"immunotherapy", re.I), "immuno"),
    (re.compile(r"medications?", re.I), "meds"),
    (re.compile(r"time[\s-]*complexity", re.I), "time-O"),
    (re.compile(r"space[\s-]*complexity", re.I), "space-O"),
    (re.compile(r"visual\s+(?:diagram\s+)?example", re.I), "visual"),
    (re.compile(r"renewable\s+energy", re.I), "renewables"),
    (re.compile(r"climate\s+change", re.I), "climate"),
    (re.compile(r"machine\s+learning", re.I), "ML"),
    (re.compile(r"artificial\s+intelligence", re.I), "AI"),
    (re.compile(r"natural\s+language\s+processing", re.I), "NLP"),
    (re.compile(r"deep\s+learning", re.I), "DL"),
    (re.compile(r"data\s+(?:set|analysis|science)", re.I), "data"),
    (re.compile(r"business\s+plan", re.I), "biz-plan"),
    (re.compile(r"marketing\s+strategy", re.I), "mktg"),
    (re.compile(r"software\s+engineer(?:ing)?", re.I), "sw-eng"),
    (re.compile(r"code\s+review", re.I), "code-review"),
]


class SemanticCompressor:
    """Layer 3: collapse prompts to semantic anchors at maximum compression."""

    def compress(self, text: str) -> str:
        result = text

        # Apply compound reductions first.
        for pattern, replacement in _COMPOUND_REDUCTIONS:
            result = pattern.sub(replacement, result)

        # Strip stop words.
        result = _STOP_WORDS.sub("", result)

        # Collapse whitespace around operators.
        result = re.sub(r"\s*\+\s*", "+", result)
        result = re.sub(r"\s*>>\s*", " >> ", result)

        # Keep only meaningful tokens (strip punctuation).
        tokens: list[str] = []
        for tok in result.split():
            tok = tok.strip(".,;:!?(){}\"'")
            if not tok or len(tok) <= 1:
                continue
            tokens.append(tok)

        result = " ".join(tokens)

        # Collapse adjacent plain words into "+" joined form.
        parts: list[str] = []
        buf: list[str] = []
        for tok in result.split():
            if _OPERATOR_PREFIX.match(tok) or "+" in tok or tok == ">>":
                if buf:
                    parts.append("+".join(w.lower() for w in buf))
                    buf = []
                parts.append(tok)
            else:
                buf.append(tok)
        if buf:
            parts.append("+".join(w.lower() for w in buf))

        result = " ".join(p for p in parts if p and p != "+")

        # Convert "explain" patterns to compact notation.
        result = re.sub(r"\bexplain[+:]([\w+-]+)", r"?\1", result)
        result = re.sub(r"\bexplain\b", "?", result)

        # Deduplicate >> operators.
        result = re.sub(r"(>>\s*)+", ">> ", result)

        # Global deduplication: collect all content words, keep only first
        # occurrence.  Operator-prefixed tokens are always kept.
        # At tok:3, also absorb standalone words that are sub-strings of
        # already-seen compound tokens (e.g. "meds" is redundant if "drugs"
        # is already present).
        seen: set[str] = set()
        deduped: list[str] = []
        for tok in result.split():
            if _OPERATOR_PREFIX.match(tok) or tok == ">>":
                deduped.append(tok)
                continue
            if "+" in tok:
                items = tok.split("+")
                unique = []
                for item in items:
                    low = item.strip().lower()
                    if low and low not in seen and not self._is_redundant(low, seen):
                        seen.add(low)
                        unique.append(item.strip())
                if unique:
                    deduped.append("+".join(unique))
            else:
                low = tok.strip().lower()
                if low and low not in seen and not self._is_redundant(low, seen):
                    seen.add(low)
                    deduped.append(tok)

        result = " ".join(deduped)

        # Final cleanup.
        result = re.sub(r"\+\+", "+", result)
        result = re.sub(r"  +", " ", result).strip()

        return result

    @staticmethod
    def _is_redundant(word: str, seen: set[str]) -> bool:
        """Check if *word* is semantically redundant given already-seen tokens.

        A word is redundant if it shares a root with an existing token
        or belongs to the same semantic cluster.
        """
        # Semantic clusters: words in the same cluster are interchangeable.
        _CLUSTERS: list[set[str]] = [
            {"drugs", "meds", "medications", "drug", "med", "medication", "pharmacology"},
            {"mechanism", "action", "moa", "how"},
            {"effects", "side-effects", "adverse", "toxicity", "risks"},
            {"protocols", "treatment", "therapy", "regimen", "trials", "clinical",
             "emerging-tx", "emerging", "novel", "new", "immuno", "immunotherapy", "immune"},
            {"cancer", "tumor", "oncology", "neoplasm", "malignancy"},
            {"complexity", "time-o", "space-o", "big-o", "performance"},
            {"visual", "diagram", "chart", "illustration", "figure"},
            {"steps", "step-by-step", "sequential", "procedure", "process"},
            {"review", "audit", "check", "inspect", "code-review"},
            {"summary", "summarize", "overview", "recap", "brief"},
        ]
        for cluster in _CLUSTERS:
            if word in cluster and seen & cluster:
                return True
        # Also check if word is a substring of any seen token.
        for s in seen:
            if len(word) >= 3 and (word in s or s in word):
                return True
        return False

    def decompress(self, text: str) -> str:
        """Semantic decompression is inherently lossy; return as-is."""
        return text
