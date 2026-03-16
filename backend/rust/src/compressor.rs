use crate::layers::lexical::LexicalCompressor;
use crate::layers::structural::StructuralCompressor;
use crate::layers::semantic::SemanticCompressor;
use crate::tokenizer::count_tokens;
use crate::system_prompt::get_system_prompt;

/// Compression level matching the tok:N notation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Level {
    /// tok:0 — no compression.
    Natural = 0,
    /// tok:1 — ~30-50% reduction (lexical only).
    Light = 1,
    /// tok:2 — ~60-80% reduction (lexical + structural).
    Medium = 2,
    /// tok:3 — ~85-95% reduction (all three layers).
    Max = 3,
}

impl Level {
    pub fn from_u8(n: u8) -> Self {
        match n {
            0 => Level::Natural,
            1 => Level::Light,
            2 => Level::Medium,
            3 => Level::Max,
            _ => Level::Medium,
        }
    }

    fn code(&self) -> &'static str {
        match self {
            Level::Natural => "0",
            Level::Light => "1",
            Level::Medium => "2",
            Level::Max => "3",
        }
    }
}

/// Core TokReducer compressor.
pub struct TokReducer {
    pub level: Level,
    pub bidirectional: bool,
    pub skip_below_tokens: usize,
    lexical: LexicalCompressor,
    structural: StructuralCompressor,
    semantic: SemanticCompressor,
}

impl TokReducer {
    pub fn new(level: Level) -> Self {
        Self {
            level,
            bidirectional: false,
            skip_below_tokens: 0,
            lexical: LexicalCompressor::new(),
            structural: StructuralCompressor::new(),
            semantic: SemanticCompressor::new(),
        }
    }

    pub fn with_options(level: Level, bidirectional: bool, skip_below_tokens: usize) -> Self {
        Self {
            level,
            bidirectional,
            skip_below_tokens,
            lexical: LexicalCompressor::new(),
            structural: StructuralCompressor::new(),
            semantic: SemanticCompressor::new(),
        }
    }

    /// Compress a raw natural-language prompt into TokReducer notation.
    pub fn compress(&self, raw: &str) -> String {
        if self.level == Level::Natural {
            return raw.to_string();
        }

        if self.skip_below_tokens > 0 && count_tokens(raw) < self.skip_below_tokens {
            return raw.to_string();
        }

        let mut text = raw.to_string();

        // Layer 1 — Lexical (tok:1+)
        if self.level as u8 >= Level::Light as u8 {
            text = self.lexical.compress(&text);
        }

        // Layer 2 — Structural (tok:2+)
        if self.level as u8 >= Level::Medium as u8 {
            text = self.structural.compress(&text);
        }

        // Layer 3 — Semantic (tok:3 only)
        if self.level as u8 >= Level::Max as u8 {
            text = self.semantic.compress(&text);
        }

        let mut header = format!("[TOKREDUCER:1.0 tok:{}", self.level.code());
        if self.bidirectional {
            header.push_str(" respond:tok1.0");
        }
        header.push(']');

        format!("{header} {text}")
    }

    /// Decompress a TokReducer-encoded response back to natural language.
    pub fn decompress(&self, text: &str) -> String {
        let mut result = text.to_string();

        if result.starts_with("[TOKREDUCER:") {
            if let Some(end) = result.find(']') {
                result = result[end + 1..].trim_start().to_string();
            }
        }

        result = self.structural.decompress(&result);
        result = self.lexical.decompress(&result);
        result
    }

    /// Return the token count of `text`.
    pub fn count(&self, text: &str) -> usize {
        count_tokens(text)
    }

    /// Return the percentage of tokens saved by compression.
    pub fn reduction_pct(&self, raw: &str, compressed: &str) -> f64 {
        let original = count_tokens(raw);
        if original == 0 {
            return 0.0;
        }
        let header_tokens = self.header_token_count();
        let reduced = count_tokens(compressed).saturating_sub(header_tokens).max(1);
        (1.0 - reduced as f64 / original as f64) * 100.0
    }

    /// Return the system prompt that prevents length mirroring.
    pub fn system_prompt() -> &'static str {
        get_system_prompt()
    }

    fn header_token_count(&self) -> usize {
        let mut header = format!("[TOKREDUCER:1.0 tok:{}", self.level.code());
        if self.bidirectional {
            header.push_str(" respond:tok1.0");
        }
        header.push(']');
        count_tokens(&header)
    }
}
