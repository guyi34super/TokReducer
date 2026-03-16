use tokreducer::{TokReducer, Level};

#[test]
fn test_lexical_compression_level1() {
    let tok = TokReducer::new(Level::Light);
    let raw = "Please write a detailed summary of the following text. \
               Please provide a comprehensive explanation of the key themes. \
               Include bullet points for the main ideas.";
    let compressed = tok.compress(raw);
    let reduction = tok.reduction_pct(raw, &compressed);
    assert!(
        reduction >= 30.0,
        "Expected >=30% reduction, got {reduction:.1}%"
    );
}

#[test]
fn test_structural_compression_level2() {
    let tok = TokReducer::new(Level::Medium);
    let raw = "You are an expert software engineer. \
               Please carefully review the following code for \
               bugs, performance issues, and style problems. \
               For each issue found, explain what the problem is \
               and provide a corrected version of the code. \
               Format your response as a numbered list.";
    let compressed = tok.compress(raw);
    let reduction = tok.reduction_pct(raw, &compressed);
    assert!(
        reduction >= 60.0,
        "Expected >=60% reduction, got {reduction:.1}%"
    );
}

#[test]
fn test_semantic_compression_level3() {
    let tok = TokReducer::new(Level::Max);
    let raw = "You are a world-class oncologist. Please provide a comprehensive, \
               detailed explanation of how chemotherapy works, covering the \
               mechanism of action, main drug classes, side effects, and how \
               treatment protocols are designed for different cancer types. \
               For each drug class, explain the mechanism of action in detail \
               and provide real-world examples of commonly used medications. \
               Also include a section on emerging therapies and immunotherapy \
               approaches that are currently in clinical trials.";
    let compressed = tok.compress(raw);
    let reduction = tok.reduction_pct(raw, &compressed);
    assert!(
        reduction >= 80.0,
        "Expected >=80% reduction, got {reduction:.1}%"
    );
}

#[test]
fn test_activation_header_present() {
    let tok = TokReducer::new(Level::Medium);
    let compressed = tok.compress("Summarize this document");
    assert!(compressed.contains("[TOKREDUCER:1.0"));
}

#[test]
fn test_short_prompt_skip_threshold() {
    let tok = TokReducer::with_options(Level::Medium, false, 20);
    let short = "What is 2 + 2?";
    let result = tok.compress(short);
    assert_eq!(result, short);
}

#[test]
fn test_system_prompt_contains_output_rule() {
    let sp = TokReducer::system_prompt();
    assert!(sp.contains("CRITICAL OUTPUT RULE"));
    assert!(sp.to_lowercase().contains("full") || sp.to_lowercase().contains("compressed input"));
}
