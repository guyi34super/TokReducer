"""Utilities for comparing verbose vs. compressed LLM outputs."""

from __future__ import annotations


def compare_outputs(
    verbose_output: str,
    compressed_output: str,
    tolerance: float = 0.20,
) -> dict[str, object]:
    """Compare two LLM outputs and return a comparison report.

    Parameters
    ----------
    verbose_output:
        The response generated from the uncompressed prompt.
    compressed_output:
        The response generated from the TokReducer-compressed prompt.
    tolerance:
        Maximum allowed relative difference in word count (default 20 %).

    Returns
    -------
    dict with keys:
        ``words_verbose``, ``words_compressed``, ``ratio``,
        ``within_tolerance``, ``sections_verbose``, ``sections_compressed``.
    """
    words_v = len(verbose_output.split())
    words_c = len(compressed_output.split())
    ratio = words_c / words_v if words_v else 0.0
    within = abs(1 - ratio) <= tolerance

    sections_v = _count_sections(verbose_output)
    sections_c = _count_sections(compressed_output)

    return {
        "words_verbose": words_v,
        "words_compressed": words_c,
        "ratio": round(ratio, 3),
        "within_tolerance": within,
        "sections_verbose": sections_v,
        "sections_compressed": sections_c,
    }


def _count_sections(text: str) -> int:
    """Heuristic: count markdown headings or numbered list top-level items."""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or (
            len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)"
        ):
            count += 1
    return count
