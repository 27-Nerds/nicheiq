"""Shared Snowball stemmer for all text matching in NicheIQ.

Thread-safe: uses threading.local() for per-thread Stemmer instances.
PyStemmer's C Stemmer object is NOT safe for concurrent access.
"""

import threading

from Stemmer import Stemmer as SnowballStemmer

_local = threading.local()


def _get_stemmer() -> SnowballStemmer:
    """Get thread-local Stemmer instance (created lazily, ~1us)."""
    if not hasattr(_local, "stemmer"):
        _local.stemmer = SnowballStemmer("english")
    return _local.stemmer


def stem_tokens(tokens: set[str]) -> set[str]:
    """Batch-stem tokens using Snowball algorithm (C-compiled, fast)."""
    if not tokens:
        return tokens
    return set(_get_stemmer().stemWords(list(tokens)))


def stem_word(word: str) -> str:
    """Stem a single word."""
    return _get_stemmer().stemWord(word)
