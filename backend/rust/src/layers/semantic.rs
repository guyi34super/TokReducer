use std::collections::HashSet;
use regex::Regex;

static COMPOUND_REDUCTIONS: &[(&str, &str)] = &[
    (r"(?i)mechanism\s+(?:of\s+)?action", "mechanism"),
    (r"(?i)drug\s+class(?:es)?", "drugs"),
    (r"(?i)side\s+effects?", "effects"),
    (r"(?i)treatment\s+protocols?", "protocols"),
    (r"(?i)cancer\s+types?", "cancer"),
    (r"(?i)clinical\s+trials?", "trials"),
    (r"(?i)emerging\s+therap(?:y|ies)", "emerging-tx"),
    (r"(?i)immunotherapy", "immuno"),
    (r"(?i)medications?", "meds"),
    (r"(?i)time[\s-]*complexity", "time-O"),
    (r"(?i)space[\s-]*complexity", "space-O"),
    (r"(?i)visual\s+(?:diagram\s+)?example", "visual"),
    (r"(?i)renewable\s+energy", "renewables"),
    (r"(?i)climate\s+change", "climate"),
    (r"(?i)machine\s+learning", "ML"),
    (r"(?i)artificial\s+intelligence", "AI"),
    (r"(?i)business\s+plan", "biz-plan"),
    (r"(?i)software\s+engineer(?:ing)?", "sw-eng"),
    (r"(?i)code\s+review", "code-review"),
];

static SEMANTIC_CLUSTERS: &[&[&str]] = &[
    &["drugs", "meds", "medications", "drug", "med", "medication", "pharmacology"],
    &["mechanism", "action", "moa", "how"],
    &["effects", "side-effects", "adverse", "toxicity", "risks"],
    &["protocols", "treatment", "therapy", "regimen", "trials", "clinical",
      "emerging-tx", "emerging", "novel", "new", "immuno", "immunotherapy", "immune"],
    &["cancer", "tumor", "oncology", "neoplasm", "malignancy"],
    &["complexity", "time-o", "space-o", "big-o", "performance"],
    &["visual", "diagram", "chart", "illustration", "figure"],
    &["steps", "step-by-step", "sequential", "procedure", "process"],
    &["review", "audit", "check", "inspect", "code-review"],
    &["summary", "summarize", "overview", "recap", "brief"],
];

pub struct SemanticCompressor {
    stop_words: Regex,
    compound_patterns: Vec<(Regex, String)>,
    operator_prefix: Regex,
}

impl SemanticCompressor {
    pub fn new() -> Self {
        let stop_words = Regex::new(
            r"(?i)\b(?:the|a|an|of|for|is|it|its|this|that|these|those|with|from|into|about|me|my|your|our|how|what|when|where|which|who|whom|whose|here|there|works?|provides?|gives?|makes?|takes?|gets?|has|have|had|should|would|could|will|shall|may|might|must|do|does|did|be|been|being|am|are|was|were|all|each|every|some|any|no|not|on|in|at|to|by|up|out|off|over|under|full|or|if|as|and|so|yet|also|please|explain|describe|write|create|generate|following|main|key|important|relevant|specific|include|including|section|detail|detailed|commonly|currently|used|using|real-world|different|designed|approaches|examples)\b"
        ).unwrap();

        let compound_patterns = COMPOUND_REDUCTIONS
            .iter()
            .map(|(pat, repl)| (Regex::new(pat).unwrap(), repl.to_string()))
            .collect();

        let operator_prefix = Regex::new(r"^[@>#!?~=•]|^(?:ctx:|fmt:|eg:|only>|len[=:]|tok:|\[)").unwrap();

        Self { stop_words, compound_patterns, operator_prefix }
    }

    pub fn compress(&self, text: &str) -> String {
        let mut result = text.to_string();

        for (re, replacement) in &self.compound_patterns {
            result = re.replace_all(&result, replacement.as_str()).to_string();
        }

        result = self.stop_words.replace_all(&result, "").to_string();

        // Collapse whitespace around operators.
        let plus_ws = Regex::new(r"\s*\+\s*").unwrap();
        result = plus_ws.replace_all(&result, "+").to_string();
        let step_ws = Regex::new(r"\s*>>\s*").unwrap();
        result = step_ws.replace_all(&result, " >> ").to_string();

        // Keep only meaningful tokens.
        let tokens: Vec<String> = result
            .split_whitespace()
            .map(|t| t.trim_matches(|c: char| ".,;:!?(){}\"'".contains(c)).to_string())
            .filter(|t| !t.is_empty() && t.len() > 1)
            .collect();
        result = tokens.join(" ");

        // Collapse adjacent plain words into "+" joined form.
        let mut parts: Vec<String> = Vec::new();
        let mut buf: Vec<String> = Vec::new();
        for tok in result.split_whitespace() {
            if self.operator_prefix.is_match(tok) || tok.contains('+') || tok == ">>" {
                if !buf.is_empty() {
                    parts.push(buf.iter().map(|w| w.to_lowercase()).collect::<Vec<_>>().join("+"));
                    buf.clear();
                }
                parts.push(tok.to_string());
            } else {
                buf.push(tok.to_string());
            }
        }
        if !buf.is_empty() {
            parts.push(buf.iter().map(|w| w.to_lowercase()).collect::<Vec<_>>().join("+"));
        }
        result = parts.into_iter().filter(|p| !p.is_empty() && p != "+").collect::<Vec<_>>().join(" ");

        // Convert explain patterns.
        let explain_re = Regex::new(r"\bexplain[+:]([\w+-]+)").unwrap();
        result = explain_re.replace_all(&result, "?$1").to_string();
        let explain_bare = Regex::new(r"\bexplain\b").unwrap();
        result = explain_bare.replace_all(&result, "?").to_string();

        // Deduplicate >> operators.
        let dup_step = Regex::new(r"(>>\s*)+").unwrap();
        result = dup_step.replace_all(&result, ">> ").to_string();

        // Global deduplication with semantic clusters.
        let mut seen: HashSet<String> = HashSet::new();
        let mut deduped: Vec<String> = Vec::new();
        for tok in result.split_whitespace() {
            if self.operator_prefix.is_match(tok) || tok == ">>" {
                deduped.push(tok.to_string());
                continue;
            }
            if tok.contains('+') {
                let items: Vec<&str> = tok.split('+').collect();
                let unique: Vec<&str> = items
                    .into_iter()
                    .filter(|item| {
                        let low = item.trim().to_lowercase();
                        if low.is_empty() || seen.contains(&low) || Self::is_redundant(&low, &seen) {
                            false
                        } else {
                            seen.insert(low);
                            true
                        }
                    })
                    .collect();
                if !unique.is_empty() {
                    deduped.push(unique.join("+"));
                }
            } else {
                let low = tok.trim().to_lowercase();
                if !low.is_empty() && !seen.contains(&low) && !Self::is_redundant(&low, &seen) {
                    seen.insert(low);
                    deduped.push(tok.to_string());
                }
            }
        }
        result = deduped.join(" ");

        // Final cleanup.
        let dup_plus = Regex::new(r"\+\+").unwrap();
        result = dup_plus.replace_all(&result, "+").to_string();
        let dup_space = Regex::new(r"  +").unwrap();
        result = dup_space.replace_all(&result, " ").trim().to_string();

        result
    }

    fn is_redundant(word: &str, seen: &HashSet<String>) -> bool {
        for cluster in SEMANTIC_CLUSTERS {
            if cluster.contains(&word) && cluster.iter().any(|c| seen.contains(*c)) {
                return true;
            }
        }
        for s in seen {
            if word.len() >= 3 && (word.contains(s.as_str()) || s.contains(word)) {
                return true;
            }
        }
        false
    }

    pub fn decompress(&self, text: &str) -> String {
        text.to_string()
    }
}

impl Default for SemanticCompressor {
    fn default() -> Self {
        Self::new()
    }
}
