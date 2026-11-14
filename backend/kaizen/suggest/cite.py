"""The citation check (NFR2): a quote counts only if its words appear, in order, in the passage.

P3 says any suggestion whose quote is not found in its source is dropped. The check compares
words, not characters, so it ignores case, punctuation, curly quotes and line breaks, which
change when text is copied out of a PDF or retyped by a model. It does not accept a quote with
a word changed, added or left out, and it does not accept "..." to join two parts of a passage:
the model is asked for one unbroken quote, and a stitched one can say something the source
does not.
"""

from __future__ import annotations

import re
import unicodedata

# Five or fewer common words ("the patient and the family") turn up in almost any passage, so
# a match that short proves nothing about where a claim came from.
MIN_QUOTE_WORDS = 6

_WORD = re.compile(r"\w+")
# A word split across two lines by PDF extraction, as in "pre-\nscription".
_BROKEN_WORD = re.compile(r"(\w)-[ \t]*\r?\n[ \t]*(\w)")


def words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text)
    text = _BROKEN_WORD.sub(r"\1\2", text)
    return _WORD.findall(text.casefold())


def quote_in_passage(quote: str, passage: str) -> bool:
    if "..." in quote or "…" in quote:
        return False
    wanted = words(quote)
    if len(wanted) < MIN_QUOTE_WORDS:
        return False
    # Spaces on both sides, so a quote can only match whole words.
    return f" {' '.join(wanted)} " in f" {' '.join(words(passage))} "
