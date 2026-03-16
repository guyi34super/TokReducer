import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Return the number of tokens in *text* using the cl100k_base encoding."""
    return len(_ENCODING.encode(text))
