use tiktoken_rs::cl100k_base;

/// Count the number of tokens in `text` using the cl100k_base encoding.
pub fn count_tokens(text: &str) -> usize {
    let bpe = cl100k_base().expect("failed to load cl100k_base encoding");
    bpe.encode_with_special_tokens(text).len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_count_tokens_basic() {
        let count = count_tokens("Hello, world!");
        assert!(count > 0);
        assert!(count < 10);
    }

    #[test]
    fn test_count_tokens_empty() {
        assert_eq!(count_tokens(""), 0);
    }
}
