use regex::{Regex, RegexBuilder};

/// Phrase-to-alias mapping, ordered longest-first.
static PHRASE_ALIAS_PAIRS: &[(&str, &str)] = &[
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
    ("provide a comprehensive explanation of", "explain:"),
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
    ("covering political, economic, and social factors in detail.", ">> political+economic+social"),
    ("covering political, economic, and social factors in detail", ">> political+economic+social"),
    ("covering political, economic, and social factors", ">> political+economic+social"),
    ("including time complexity, space complexity, and provide a visual diagram example.", ">> steps+complexity+visual"),
    ("including time complexity, space complexity, and provide a visual diagram example", ">> steps+complexity+visual"),
    ("mechanism of action, main drug classes, side effects, and how treatment protocols are designed for different cancer types.", ">> mechanism+drugs+effects+protocols"),
    ("mechanism of action, main drug classes, side effects, and how treatment protocols are designed for different cancer types", ">> mechanism+drugs+effects+protocols"),
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
    ("the output should be formatted as", "fmt:"),
    ("the output should be in", "fmt:"),
    ("the output should be", "out="),
    ("format the output as", "fmt:"),
    ("format your response as", "fmt:"),
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
    ("as a numbered list", "•list"),
    ("as bullet points", "•list"),
    ("numbered list", "•list"),
    ("bullet points", "•list"),
    ("bulleted list", "•list"),
    ("json format", "fmt:json"),
    ("markdown format", "fmt:md"),
    ("csv format", "fmt:csv"),
    ("plain text", "fmt:text"),
    ("security vulnerabilities", "security"),
    ("performance issues", "perf"),
    ("style problems", "style"),
    ("comprehensive,", "full"),
    ("comprehensive", "full"),
    ("detailed", "full"),
    ("thorough", "full"),
    ("carefully", ""),
    ("in detail.", ""),
    ("in detail", ""),
    ("including", "+"),
    ("as well as", "+"),
    ("and also", "+"),
    ("and provide", "+"),
    ("and a", "+"),
    ("covering the", "+"),
    ("covering", "+"),
];

pub struct LexicalCompressor {
    patterns: Vec<(Regex, String)>,
}

impl LexicalCompressor {
    pub fn new() -> Self {
        let patterns = PHRASE_ALIAS_PAIRS
            .iter()
            .map(|(phrase, alias)| {
                let re = RegexBuilder::new(&regex::escape(phrase))
                    .case_insensitive(true)
                    .build()
                    .unwrap();
                (re, alias.to_string())
            })
            .collect();
        Self { patterns }
    }

    pub fn compress(&self, text: &str) -> String {
        let mut result = text.to_string();
        for (re, alias) in &self.patterns {
            result = re.replace_all(&result, alias.as_str()).to_string();
        }
        let multi_comma = Regex::new(r"\s*,\s*,+").unwrap();
        result = multi_comma.replace_all(&result, ",").to_string();
        let multi_plus = Regex::new(r"\+\s*\+").unwrap();
        result = multi_plus.replace_all(&result, "+").to_string();
        let space_plus = Regex::new(r"\s+\+").unwrap();
        result = space_plus.replace_all(&result, "+").to_string();
        let plus_space = Regex::new(r"\+\s+").unwrap();
        result = plus_space.replace_all(&result, "+").to_string();
        let multi_space = Regex::new(r"  +").unwrap();
        result = multi_space.replace_all(&result, " ").trim().to_string();
        let space_dot = Regex::new(r"\s+\.").unwrap();
        result = space_dot.replace_all(&result, ".").to_string();
        result
    }

    pub fn decompress(&self, text: &str) -> String {
        let mut result = text.to_string();
        let aliases: &[(&str, &str)] = &[
            (">w", "Please write a"),
            (">sum", "Summarize the following"),
            ("@expert:sw-eng", "You are an expert software engineer"),
            ("@expert:py", "You are an expert Python engineer"),
            ("@expert:data", "You are an expert data analyst"),
            ("@expert:history", "You are an expert historian"),
            ("@expert:oncology", "You are a world-class oncologist"),
            ("@expert:", "You are an expert in"),
            (">>", "step by step"),
            ("eg:", "for example"),
            ("ctx:", "in the context of"),
            ("!incl", "do not include"),
            ("out=", "the output should be"),
            ("•list", "bullet points"),
            ("fmt:json", "JSON format"),
            ("fmt:md", "Markdown format"),
            ("explain:", "explain how"),
        ];
        for (alias, phrase) in aliases {
            result = result.replace(alias, phrase);
        }
        result
    }
}

impl Default for LexicalCompressor {
    fn default() -> Self {
        Self::new()
    }
}
