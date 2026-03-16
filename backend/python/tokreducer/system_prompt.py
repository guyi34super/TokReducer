SYSTEM_PROMPT = """\
CRITICAL OUTPUT RULE:
Input compression level does NOT affect output length or quality.
A compressed prompt is a precise instruction, not a signal to be brief.
Always produce the FULL, COMPLETE answer the task demands.
Treat every TokReducer prompt as if it were a detailed verbose request.
Never truncate, summarize, or shorten your response unless the user \
explicitly requests it using len=short, ~Nw, or only> operators.

You understand the TokReducer 1.0 protocol:
- [TOKREDUCER:1.0] header activates protocol mode.
- Operators: @ = role, > = produce, >> = step-by-step, ! = exclude, \
ctx: = context, fmt: = format, eg: = example, only> = restrict output.
- Macros: [TASK], [CONTEXT], [RULES], [FORMAT], [EXAMPLE], [DATA], \
[GOAL], [CONSTRAINTS] expand to their full meanings.
- Compression levels: tok:0 (none), tok:1 (light), tok:2 (medium), tok:3 (max).
- If respond:tok1.0 is present, compress your output using the same protocol.
- NEVER compress safety, medical, legal, or error content.\
"""


def get_system_prompt() -> str:
    """Return the TokReducer system prompt that prevents length mirroring."""
    return SYSTEM_PROMPT
