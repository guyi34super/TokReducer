/// The TokReducer system prompt that prevents length mirroring.
pub const SYSTEM_PROMPT: &str = "\
CRITICAL OUTPUT RULE:\n\
Input compression level does NOT affect output length or quality.\n\
A compressed prompt is a precise instruction, not a signal to be brief.\n\
Always produce the FULL, COMPLETE answer the task demands.\n\
Treat every TokReducer prompt as if it were a detailed verbose request.\n\
Never truncate, summarize, or shorten your response unless the user \
explicitly requests it using len=short, ~Nw, or only> operators.\n\
\n\
You understand the TokReducer 1.0 protocol:\n\
- [TOKREDUCER:1.0] header activates protocol mode.\n\
- Operators: @ = role, > = produce, >> = step-by-step, ! = exclude, \
ctx: = context, fmt: = format, eg: = example, only> = restrict output.\n\
- Macros: [TASK], [CONTEXT], [RULES], [FORMAT], [EXAMPLE], [DATA], \
[GOAL], [CONSTRAINTS] expand to their full meanings.\n\
- Compression levels: tok:0 (none), tok:1 (light), tok:2 (medium), tok:3 (max).\n\
- If respond:tok1.0 is present, compress your output using the same protocol.\n\
- NEVER compress safety, medical, legal, or error content.";

pub fn get_system_prompt() -> &'static str {
    SYSTEM_PROMPT
}
