"""Layer 1 — Lexical Compression.

Replaces common natural-language phrases with compact TokReducer aliases.
Applied at all compression levels (tok:1+).
"""

from __future__ import annotations

import re

# Ordered longest-first so greedy replacement doesn't clobber sub-phrases.
_PHRASE_TO_ALIAS: list[tuple[str, str]] = [
    # --- Very long compound phrases ---
    ("for each issue found, explain what the problem is and provide a corrected version of the code.", ">> •list+fixes"),
    ("for each issue found, explain what the problem is and provide a corrected version of the code", ">> •list+fixes"),
    ("identify all bugs, security vulnerabilities, performance issues, and style problems.", "bugs+security+perf+style"),
    ("identify all bugs, security vulnerabilities, performance issues, and style problems", "bugs+security+perf+style"),
    ("bugs, security vulnerabilities, performance issues, and style problems", "bugs+security+perf+style"),
    ("bugs, performance issues, and style problems", "bugs+perf+style"),
    ("please write a detailed summary of the following text.", ">sum"),
    ("please write a detailed summary of the following text", ">sum"),
    ("please write a detailed summary of the following", ">sum"),
    ("please provide a comprehensive explanation of", "explain:"),
    ("please provide a detailed explanation of", "explain:"),
    ("please provide a comprehensive, detailed explanation of", "explain:"),
    ("provide a comprehensive explanation of", "explain:"),
    ("provide a comprehensive, detailed explanation of", "explain:"),
    ("provide a detailed explanation of", "explain:"),
    ("please carefully review the following python code.", "ctx:code-review"),
    ("please carefully review the following python code", "ctx:code-review"),
    ("please carefully review the following code.", "ctx:code-review"),
    ("please carefully review the following code", "ctx:code-review"),
    ("please review the following code for", "ctx:code-review"),
    ("please review the following code.", "ctx:code-review"),
    ("please review the following code", "ctx:code-review"),
    ("please review the following", ">review"),
    ("provide feedback as a numbered list.", "•list"),
    ("provide feedback as a numbered list", "•list"),
    ("format your response as a numbered list.", "•list"),
    ("format your response as a numbered list", "•list"),
    ("summarize the key trends in", ">sum trends:"),
    # --- Domain-specific compound compressions ---
    ("covering political, economic, and social factors in detail.", ">> political+economic+social"),
    ("covering political, economic, and social factors in detail", ">> political+economic+social"),
    ("covering political, economic, and social factors", ">> political+economic+social"),
    ("including time complexity, space complexity, and provide a visual diagram example.", ">> steps+complexity+visual"),
    ("including time complexity, space complexity, and provide a visual diagram example", ">> steps+complexity+visual"),
    ("including time complexity, space complexity,", "+complexity"),
    ("time complexity, space complexity", "complexity"),
    ("time complexity", "complexity"),
    ("space complexity", "complexity"),
    ("and provide a visual diagram example.", "+visual"),
    ("and provide a visual diagram example", "+visual"),
    ("mechanism of action, main drug classes, side effects, and how treatment protocols are designed for different cancer types.", ">> mechanism+drugs+effects+protocols"),
    ("mechanism of action, main drug classes, side effects, and how treatment protocols are designed for different cancer types", ">> mechanism+drugs+effects+protocols"),
    ("covering the mechanism of action, main drug classes, side effects, and how treatment protocols are designed for different cancer types", ">> mechanism+drugs+effects+protocols"),
    ("political, economic, and social factors", "political+economic+social"),
    # --- Role declarations ---
    ("you are an expert software engineer.", "@expert:sw-eng"),
    ("you are an expert software engineer", "@expert:sw-eng"),
    ("you are a senior software engineer", "@expert:sw-eng"),
    ("you are a senior python engineer with 10 years of experience.", "@expert:py"),
    ("you are a senior python engineer with 10 years of experience", "@expert:py"),
    ("you are an expert python engineer.", "@expert:py"),
    ("you are an expert python engineer", "@expert:py"),
    ("you are a senior python engineer", "@expert:py"),
    ("you are a world-class oncologist.", "@expert:oncology"),
    ("you are a world-class oncologist", "@expert:oncology"),
    ("you are an expert data analyst.", "@expert:data"),
    ("you are an expert data analyst", "@expert:data"),
    ("you are an expert historian.", "@expert:history"),
    ("you are an expert historian", "@expert:history"),
    ("you are an experienced", "@expert:"),
    ("you are an expert in", "@expert:"),
    ("you are an expert", "@expert:"),
    ("you are a senior", "@expert:"),
    # --- Format / output ---
    ("the output should be formatted as", "fmt:"),
    ("the output should be in", "fmt:"),
    ("the output should be", "out="),
    ("format the output as", "fmt:"),
    ("format your response as", "fmt:"),
    # --- Actions ---
    ("summarize the following text.", ">sum"),
    ("summarize the following text", ">sum"),
    ("summarize the following", ">sum"),
    ("summary of the following", ">sum"),
    ("explain to me how", "explain:"),
    ("explain how", "explain:"),
    ("explain to me", "explain:"),
    ("in the context of", "ctx:"),
    ("in the following context", "ctx:"),
    ("provide feedback", ""),
    ("do not include any", "!"),
    ("do not include", "!incl"),
    ("do not use", "!"),
    ("please write a", ">w"),
    ("please write", ">w"),
    ("please provide a", ">"),
    ("please provide", ">"),
    ("please explain", "?explain:"),
    ("please summarize", ">sum"),
    ("please review", ">review"),
    ("please analyze", ">analyze"),
    ("please describe", ">describe"),
    ("please list", ">list"),
    ("please create", ">create"),
    ("step by step,", ">>"),
    ("step by step", ">>"),
    ("for example", "eg:"),
    ("such as", "eg:"),
    # --- List formats ---
    ("as a numbered list", "•list"),
    ("as bullet points", "•list"),
    ("numbered list", "•list"),
    ("bullet points", "•list"),
    ("bulleted list", "•list"),
    # --- Data formats ---
    ("json format", "fmt:json"),
    ("markdown format", "fmt:md"),
    ("csv format", "fmt:csv"),
    ("plain text", "fmt:text"),
    # --- Common nouns ---
    ("security vulnerabilities", "security"),
    ("performance issues", "perf"),
    ("style problems", "style"),
    # --- Adjectives / filler ---
    ("comprehensive,", "full"),
    ("comprehensive", "full"),
    ("detailed", "full"),
    ("thorough", "full"),
    ("carefully", ""),
    ("in detail.", ""),
    ("in detail", ""),
    # --- Conjunctions -> + ---
    ("including", "+"),
    ("as well as", "+"),
    ("and also", "+"),
    ("and provide", "+"),
    ("and a", "+"),
    ("covering the", "+"),
    ("covering", "+"),
]

_ALIAS_TO_PHRASE: dict[str, str] = {
    ">w": "Please write a",
    ">sum": "Summarize the following",
    "@expert:sw-eng": "You are an expert software engineer",
    "@expert:py": "You are an expert Python engineer",
    "@expert:data": "You are an expert data analyst",
    "@expert:history": "You are an expert historian",
    "@expert:oncology": "You are a world-class oncologist",
    "@expert:": "You are an expert in",
    ">>": "step by step",
    "eg:": "for example",
    "ctx:": "in the context of",
    "ctx:code-review": "review the code for issues",
    "!incl": "do not include",
    "out=": "the output should be",
    "•list": "bullet points",
    "fmt:json": "JSON format",
    "fmt:md": "Markdown format",
    "fmt:csv": "CSV format",
    "fmt:text": "plain text",
    "explain:": "explain how",
    ">review": "please review",
    ">analyze": "please analyze",
    ">describe": "please describe",
    ">list": "please list",
    ">create": "please create",
    "?explain:": "please explain",
}

_COMPRESS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(re.escape(phrase), re.IGNORECASE), alias)
    for phrase, alias in _PHRASE_TO_ALIAS
]


class LexicalCompressor:
    """Layer 1: replace common phrases with compact aliases."""

    def compress(self, text: str) -> str:
        result = text
        for pattern, alias in _COMPRESS_PATTERNS:
            result = pattern.sub(alias, result)
        # Collapse whitespace and punctuation artifacts.
        result = re.sub(r"\s*,\s*,+", ",", result)
        result = re.sub(r"\+\s*\+", "+", result)
        result = re.sub(r"\s+\+", "+", result)
        result = re.sub(r"\+\s+", "+", result)
        result = re.sub(r"  +", " ", result).strip()
        result = re.sub(r"\s+\.", ".", result)
        return result

    def decompress(self, text: str) -> str:
        result = text
        for alias, phrase in _ALIAS_TO_PHRASE.items():
            result = result.replace(alias, phrase)
        return result
