"""Tokenizing for the lexical arms: whole words, lowercase, plural folding only."""
from __future__ import annotations

import re

# The package's current stoplist (memento_tattoo.recall.TERM_STOPLIST). BM25's
# inverse document frequency handles the remaining common words.
STOPLIST = frozenset({"the", "and", "for", "that", "this", "with", "memory", "memento"})

_WORD = re.compile(r"[a-z0-9]+")


def s_stem(word: str) -> str:
    """Harman's S-stemmer (1991): fold plurals with three ordered rules.

    1. "ies" -> "y", unless the word ends in "eies" or "aies".
    2. "es" -> "e", unless the word ends in "aes", "ees" or "oes".
    3. "s" -> "", unless the word ends in "us" or "ss".

    Only the first matching rule applies. Words of three letters or fewer are
    left alone, so short tokens such as "gas" or "its" do not lose a letter.
    """
    if len(word) <= 3:
        return word
    if word.endswith("ies") and not word.endswith(("eies", "aies")):
        return word[:-3] + "y"
    if word.endswith("es") and not word.endswith(("aes", "ees", "oes")):
        return word[:-1]
    if word.endswith("s") and not word.endswith(("us", "ss")):
        return word[:-1]
    return word


def tokens(text: str, *, stoplist: frozenset[str] = STOPLIST) -> list[str]:
    """Whole-word tokens with plural folding. "art" never matches "start"."""
    out = []
    for word in _WORD.findall(text.lower()):
        if word in stoplist or (len(word) < 2 and not word.isdigit()):
            continue
        out.append(s_stem(word))
    return out
