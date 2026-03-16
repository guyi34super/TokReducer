use regex::Regex;

static STRUCTURAL_PATTERNS: &[(&str, &str)] = &[
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
];

static MACROS: &[(&str, &str)] = &[
    ("[TASK]", "The task I need you to complete is:"),
    ("[CONTEXT]", "Here is the relevant background context:"),
    ("[RULES]", "Follow these rules strictly:"),
    ("[FORMAT]", "The output format should be:"),
    ("[EXAMPLE]", "Here is an example input/output pair:"),
    ("[DATA]", "Here is the data to process:"),
    ("[GOAL]", "The end goal of this task is:"),
    ("[CONSTRAINTS]", "You must stay within these constraints:"),
];

pub struct StructuralCompressor {
    patterns: Vec<(Regex, String)>,
    filler: Regex,
    conjunction: Regex,
    redundant_after_review: Regex,
}

impl StructuralCompressor {
    pub fn new() -> Self {
        let patterns = STRUCTURAL_PATTERNS
            .iter()
            .map(|(phrase, macro_)| {
                let re = Regex::new(&format!("(?i){}", regex::escape(phrase))).unwrap();
                (re, macro_.to_string())
            })
            .collect();

        let filler = Regex::new(
            r"(?i)\b(?:the|a|an|of|for|is|it|its|this|that|these|those|with|from|into|about|between|through|during|very|really|just|also|then|so|but|could you|can you|would you|i need you to|i want you to|i would like you to|make sure to|be sure to|ensure that|please note that|note that|keep in mind that|it is important to|it's important to|here is|here are)\b"
        ).unwrap();

        let conjunction = Regex::new(
            r"(?i)\s*,?\s*(?:and|as well as|along with|together with|in addition to)\s+"
        ).unwrap();

        let redundant_after_review = Regex::new(
            r"(?i)(ctx:code-review)\s*(?:>>)?\s*(?:bugs?\+?|security\+?|perf\+?|style\+?|issues?\+?)*"
        ).unwrap();

        Self { patterns, filler, conjunction, redundant_after_review }
    }

    pub fn compress(&self, text: &str) -> String {
        let mut result = text.to_string();

        for (re, macro_) in &self.patterns {
            result = re.replace_all(&result, macro_.as_str()).to_string();
        }

        result = self.conjunction.replace_all(&result, "+").to_string();
        result = self.filler.replace_all(&result, "").to_string();

        let comma = Regex::new(r"\s*,\s*").unwrap();
        result = comma.replace_all(&result, "+").to_string();

        result = self.redundant_after_review.replace_all(&result, "$1 >>").to_string();

        // Cleanup
        for (pattern, replacement) in &[
            (r"\+\+", "+"),
            (r"\s+\+", "+"),
            (r"\+\s+", "+"),
            (r"\.+\s*", " "),
            (r">> >>", ">>"),
            (r"  +", " "),
        ] {
            let re = Regex::new(pattern).unwrap();
            result = re.replace_all(&result, *replacement).to_string();
        }

        result.trim().to_string()
    }

    pub fn decompress(&self, text: &str) -> String {
        let mut result = text.to_string();
        for (macro_, expansion) in MACROS {
            result = result.replace(macro_, expansion);
        }
        let role_re = Regex::new(r"@expert:([\w-]+)").unwrap();
        result = role_re.replace_all(&result, |caps: &regex::Captures| {
            let role = caps[1].replace('-', " ");
            format!("You are an expert {role}")
        }).to_string();
        let ctx_re = Regex::new(r"ctx:([\w-]+)").unwrap();
        result = ctx_re.replace_all(&result, "in the context of $1").to_string();
        result
    }
}

impl Default for StructuralCompressor {
    fn default() -> Self {
        Self::new()
    }
}
