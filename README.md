# TokReducer 1.0

Token Compression Protocol for Large Language Models.

Reduce token consumption by up to 95% — save money, save energy, same complete answers.

## Overview

TokReducer compresses LLM prompts using three layers:

| Layer | Name | Applied at | Reduction |
|-------|------|-----------|-----------|
| L1 | Lexical | tok:1+ | ~30-50% |
| L2 | Structural | tok:2+ | ~60-80% |
| L3 | Semantic | tok:3 | ~85-95% |

**The golden rule**: compressed input never means compressed output. The LLM receives fewer tokens as instructions, but its answer is exactly as complete as if it received a full verbose prompt.

## Installation

### Python

```bash
pip install -e "./backend/python"

# With all optional dependencies (API server, LLM clients)
pip install -e "./backend/python[all]"

# With test dependencies
pip install -e "./backend/python[testing]"
```

### Rust

The Rust implementation provides a high-performance compression engine. When `RUST_COMPRESSOR_URL` is set, the Python backend delegates all compression to the Rust service.

```bash
cd backend/rust
cargo build --lib

# With CLI (REST API server for compress/decompress)
cargo build --features cli
```

Run the Rust compressor locally: `tokreducer-cli serve --port 8081`, then set `RUST_COMPRESSOR_URL=http://localhost:8081`.

### Docker

```bash
# Start everything (rust-compressor + backend + frontend)
docker compose up --build

# Rust compressor (internal): http://rust-compressor:8081
# Backend at http://localhost:8080, Dashboard at http://localhost:3000
```

When running in Docker, the Python backend uses the Rust compressor service for all compress/decompress operations. Set `RUST_COMPRESSOR_URL` in `.env` to override (e.g. for local dev with Rust running separately).

## Python Usage

### Basic Compression

```python
from tokreducer import TokReducer, Level

tok = TokReducer(level=Level.MEDIUM)  # tok:2

raw = "You are an expert Python engineer. Please review this code for bugs, performance issues, and style problems. Format the output as a numbered list."
compressed = tok.compress(raw)

print(f"Original tokens: {tok.count(raw)}")
print(f"Compressed tokens: {tok.count(compressed)}")
print(f"Reduction: {tok.reduction_pct(raw, compressed):.1f}%")
```

### With OpenAI

```python
from tokreducer import TokReducer, Level
import openai

tok = TokReducer(level=Level.MEDIUM)
client = openai.OpenAI(api_key="YOUR_KEY")

prompt = "Summarize the key trends in renewable energy in 2024"
compressed = tok.compress(prompt)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": tok.system_prompt()},
        {"role": "user", "content": compressed},
    ],
)
print(response.choices[0].message.content)
```

### With Anthropic Claude

```python
from tokreducer import TokReducer, Level
import anthropic

tok = TokReducer(level=Level.MEDIUM, bidirectional=True)
client = anthropic.Anthropic(api_key="YOUR_KEY")

compressed = tok.compress("Write a full business plan for a SaaS startup")
message = client.messages.create(
    model="claude-opus-4-20250514",
    max_tokens=4096,
    system=tok.system_prompt(),
    messages=[{"role": "user", "content": compressed}],
)
result = tok.decompress(message.content[0].text)
print(result)
```

### Middleware Decorator

```python
from tokreducer import middleware

@middleware(level=2, bidirectional=True)
def ask_llm(prompt: str) -> str:
    return call_your_llm_api(prompt)

answer = ask_llm("Write a comprehensive analysis of climate policy options")
```

### REST API

```bash
# Start the server
tokreducer serve --port 8080 --level 2

# Compress a prompt
curl -X POST http://localhost:8080/compress \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "You are an expert in Python...", "level": 2}'

# Full pipeline: compress -> LLM -> decompress
curl -X POST http://localhost:8080/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Write a full marketing strategy...", "level": 2, "provider": "openai", "model": "gpt-4o"}'
```

## Rust Usage

### Library

```rust
use tokreducer::{TokReducer, Level};

fn main() {
    let tok = TokReducer::new(Level::Medium);

    let raw = "You are an expert data analyst. Analyze this CSV dataset.";
    let compressed = tok.compress(raw);

    println!("Original tokens: {}", tok.count(raw));
    println!("Compressed: {compressed}");
    println!("System prompt: {}", TokReducer::system_prompt());
}
```

### CLI

```bash
# Compress a prompt
cargo run --features cli -- compress "You are an expert..." --level 2

# Start REST API server
cargo run --features cli -- serve --port 8080 --level 2
```

## Running Tests

### Python Unit Tests (no API key needed)

```bash
cd backend/python
pip install -e ".[testing]"
pytest tests/test_compression.py -v
```

### Python Integration Tests (requires OPENAI_API_KEY)

```bash
export OPENAI_API_KEY=your_key_here
pytest tests/ -v --tb=short
```

### Rust Tests

```bash
cd backend/rust
cargo test
```

### Test Coverage

| Test File | What It Proves | Tests |
|-----------|---------------|-------|
| test_compression.py | Input tokens are genuinely reduced | 6 |
| test_output_completeness.py | Output is full quality despite compression | 4 |
| test_code_review.py | Code review finds all bugs + provides fixes | 4 |
| test_document_writing.py | Full documents produced, not stubs | 4 |
| test_data_analysis.py | All metrics analyzed, correct format output | 3 |
| test_no_mirroring.py | Short input does NOT produce short output | 4 |

## Compression Levels

| Level | Code | Reduction | Use Case |
|-------|------|-----------|----------|
| Natural | tok:0 | 0% | Normal conversation |
| Light | tok:1 | ~30-50% | Casual use |
| Medium | tok:2 | ~60-80% | API calls, structured tasks |
| Maximum | tok:3 | ~85-95% | Bulk processing, cost-critical |

## Syntax Quick Reference

| Category | Code | Meaning |
|----------|------|---------|
| Activate | `[TOKREDUCER:1.0]` | Enable protocol |
| Level | `tok:0/1/2/3` | Compression level |
| Role | `@expert:X` | You are an expert in X |
| Generate | `> X` | Write / produce X |
| Steps | `>> X` | Do X step by step |
| Context | `ctx:X` | In the context of X |
| Exclude | `!X` | Do not include X |
| Format | `fmt:X` | Output format is X |
| Combine | `X+Y+Z` | Include all of X, Y, Z |
| Question | `?explain:X` | Explain X |
| Summary | `>sum` | Summarize |
| List | `•list` | Bullet point list |


