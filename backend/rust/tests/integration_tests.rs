use tokreducer::{TokReducer, Level};

#[test]
fn test_compress_decompress_roundtrip() {
    let tok = TokReducer::new(Level::Medium);
    let raw = "Please write a detailed summary of the following text.";
    let compressed = tok.compress(raw);
    let decompressed = tok.decompress(&compressed);
    assert!(!decompressed.is_empty());
    assert!(!decompressed.contains("[TOKREDUCER:"));
}

#[test]
fn test_natural_level_passthrough() {
    let tok = TokReducer::new(Level::Natural);
    let raw = "Hello, world!";
    assert_eq!(tok.compress(raw), raw);
}

#[test]
fn test_bidirectional_header() {
    let tok = TokReducer::with_options(Level::Medium, true, 0);
    let compressed = tok.compress("Summarize this document");
    assert!(compressed.contains("respond:tok1.0"));
}

#[test]
fn test_count_tokens() {
    let tok = TokReducer::new(Level::Medium);
    let count = tok.count("Hello, world!");
    assert!(count > 0);
    assert!(count < 10);
}

#[test]
fn test_reduction_pct_positive() {
    let tok = TokReducer::new(Level::Medium);
    let raw = "You are an expert software engineer. \
               Please carefully review the following code for \
               bugs, performance issues, and style problems. \
               For each issue found, explain what the problem is \
               and provide a corrected version of the code.";
    let compressed = tok.compress(raw);
    let pct = tok.reduction_pct(raw, &compressed);
    assert!(pct > 0.0, "Expected positive reduction, got {pct:.1}%");
}
