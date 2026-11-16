"""Rules that drop PERSON tags on words that are not names (FR2, P3 Table 9).

On 1,625 real ambulance comments, spaCy tagged 33 spans as PERSON and only one was a
name. The rest were kinship words ("Mum", "My Dad"), a hospital and the ambulance
service written as acronyms, a town, drug names (some misspelt), conditions, typos and
truncated words, and sentence-initial words such as "However". The rules below remove
those tags. They work on the shape of the word, short word lists, and the dictionary and
stop words that ship inside the pinned spaCy model, so nothing extra is downloaded.

A tag is trimmed from both ends, one word at a time, while the end word can never be a
name (see `_never_a_name`). "My Dad" and "Game Dexamethasone" lose every word that way.
If a single word is left and no cue found it (see `CuedNameRecognizer`), the
context rules in `_ordinary_word_in_context` decide whether spaCy misread an ordinary
word as a name. A name found by a cue ("nurse Rose", "my daughter Grace") is only ever
trimmed, never dropped by context, because the cue is better evidence than the word.
"""

from __future__ import annotations

import difflib
import re
from functools import lru_cache

from spacy.lang.en.stop_words import STOP_WORDS
from spacy.language import Language
from spacy.tokens import Doc

# Family and care roles. Patients write "Mum", "my Dad", "Dads age", "Gran's carer";
# none of these is a name. Plurals and possessives are handled in `_base`.
KINSHIP_AND_ROLE = {
    "mum", "mam", "mom", "mommy", "mummy", "mother", "dad", "daddy", "father", "parent",
    "gran", "granny", "grandma", "grandmother", "nan", "nana", "nanna", "nanny", "grandad",
    "granddad", "grandpa", "grandfather", "grandparent", "wife", "husband", "partner", "son",
    "daughter", "child", "baby", "sister", "brother", "sibling", "aunt", "auntie", "aunty",
    "uncle", "niece", "nephew", "cousin", "grandson", "granddaughter", "grandchild", "fiance",
    "fiancee", "friend", "neighbour", "neighbor", "carer", "caregiver",
    "nurse", "paramedic", "medic", "doctor", "dr", "gp", "consultant", "surgeon", "midwife",
    "technician", "crew", "driver", "porter", "receptionist", "physio", "handler", "staff",
    "pt", "pts", "rn", "rpn", "np", "md", "er", "ed", "icu", "iv", "prn",
}
_POSSESSIVE = {"my", "our", "his", "her", "their", "your", "the", "a", "an"}

# Drugs and conditions that come up in ambulance and ED feedback. Misspellings are
# common ("Entinox", "medazalam"), so `_is_drug_or_condition` also accepts close matches.
DRUGS_AND_CONDITIONS = {
    "entonox", "penthrox", "methoxyflurane", "midazolam", "buccolam", "diazepam", "lorazepam",
    "morphine", "codeine", "fentanyl", "ketamine", "tramadol", "paracetamol", "ibuprofen",
    "naproxen", "aspirin", "calpol", "nurofen", "dexamethasone", "prednisolone",
    "hydrocortisone", "salbutamol", "ventolin", "ipratropium", "adrenaline", "epinephrine",
    "epipen", "naloxone", "ondansetron", "metoclopramide", "cyclizine", "glucagon", "insulin",
    "amoxicillin", "penicillin", "warfarin", "heparin", "apixaban", "rivaroxaban", "clopidogrel",
    "furosemide", "atropine", "amiodarone", "oramorph", "gtn", "nitroglycerin",
    "covid", "coronavirus", "deafblind", "dementia", "alzheimers", "parkinsons", "sepsis",
    "croup", "asthma", "copd", "diabetes", "epilepsy", "stroke", "angina", "pneumonia",
    "alstrom", "anaphylaxis",
}
_FUZZY_CUTOFF = 0.75  # "medazalam" vs "midazolam" is 0.78; names tried against the list stay below
_FUZZY_MIN_LEN = 6  # shorter words match too much ("codie" vs "codeine")

# Endings of English town names. Locations are not in FR2's list of details to remove,
# and spaCy's GPE and LOC labels are already ignored, but it sometimes calls a town a
# PERSON ("Cramlington"). Only applied to a single uncued word, so "Dr Hamilton" and
# "Rose Ashton" are still removed; "Hamilton" written alone is not.
_PLACE_ENDINGS = re.compile(
    r"(?:ington|ton|ham|ford|bury|borough|burgh|chester|caster|mouth|wick|field|pool|shire|minster|port|dale)$"
)

_VOWELS = set("aeiouy")


def _base(word: str) -> str:
    """Lower case, without a trailing possessive: "Dad's" -> "dad"."""
    return re.sub(r"['’]s?$", "", word).lower()


def _is_kinship_or_role(word: str) -> bool:
    w = _base(word)
    # "Dads" (plural or a possessive without the apostrophe) counts as "dad".
    return w in KINSHIP_AND_ROLE or (w.endswith("s") and w[:-1] in KINSHIP_AND_ROLE)


def _is_drug_or_condition(word: str) -> bool:
    w = _base(word)
    if w in DRUGS_AND_CONDITIONS:
        return True
    return len(w) >= _FUZZY_MIN_LEN and bool(
        difflib.get_close_matches(w, DRUGS_AND_CONDITIONS, n=1, cutoff=_FUZZY_CUTOFF)
    )


def _never_a_name(word: str, after_role: bool = False) -> bool:
    """True for a word that cannot be a name whatever its context.

    Names are capitalised, have a vowel, and contain only letters, hyphens and
    apostrophes. So lower case words ("covid", "fone", "forPatients"), words with no
    vowel ("Xx", "Xxx" as kisses), and words with digits or dots inside ("Friendly.put")
    are dropped. The one exception is a lower case word straight after a role or kinship
    word ("nurse daisy"), where spaCy is usually right that it is a name.

    Acronyms of 2 to 5 capitals are services and hospitals ("NEAS", "RVI"), which also
    means a name typed in capitals is missed; we judged that rarer. Stop words of five
    letters or more ("However", "Although") are never names, and a cue such as "dr."
    at the end of a sentence can pick one up. Shorter ones can be ("Will", "May").
    """
    low = word.lower()
    if low in _POSSESSIVE or (len(low) >= 5 and low in STOP_WORDS):
        return True
    if _is_kinship_or_role(word) or _is_drug_or_condition(word):
        return True
    if not word[:1].isupper() and not after_role:
        return True
    if not (_VOWELS & set(word.lower())):
        return True
    if re.search(r"[\d.]", word):
        return True
    return bool(re.fullmatch(r"[A-Z]{2,5}", word))


@lru_cache(maxsize=1)
def _dictionary(nlp: Language) -> frozenset[str]:
    """English words from the lemmatizer's lookup table inside en_core_web_lg (WordNet based).

    It also holds some first names ("sarah", "david"), which is why a dictionary word is
    only dropped when spaCy also reads it as an ordinary word once it is lower-cased.
    """
    table = nlp.get_pipe("lemmatizer").lookups.get_table("lemma_index")
    return frozenset(w for pos in table.keys() for w in table[pos])


def _is_common_word(word: str, nlp: Language) -> bool:
    w = word.lower()
    if w in STOP_WORDS or w in _dictionary(nlp):
        return True
    # Closed compounds missing from the table, such as "timescale" (time + scale).
    words = _dictionary(nlp)
    return any(w[:i] in words and w[i:] in words for i in range(3, len(w) - 2))


def _ordinary_word_in_context(doc: Doc, start: int, end: int, nlp: Language) -> bool:
    """For one uncued word: True when it is an ordinary word spaCy read as a name."""
    span = doc.char_span(start, end, alignment_mode="expand")
    if span is None or len(span) != 1:
        return False
    tok = span[0]
    word = tok.text
    low = word.lower()

    # A typo that doubles the last letter of a function word: "Fromm the beginning".
    if len(low) >= 5 and low[-1] == low[-2] and low[:-1] in STOP_WORDS:
        return True
    # A word cut off at the end of the comment: "...helped instead. Shou".
    if tok.i == len(doc) - 1 and len(low) >= 4 and any(
        s.startswith(low) and s != low for s in STOP_WORDS
    ):
        return True
    if _PLACE_ENDINGS.search(low) and len(low) >= 7:
        return True

    if not _is_common_word(word, nlp):
        return False
    prev = doc[tok.i - 1] if tok.i > 0 else None
    after_determiner = prev is not None and prev.pos_ == "DET"  # "the Hill"
    if not (tok.is_sent_start or after_determiner or tok.pos_ != "PROPN"):
        # A capitalised dictionary word in mid-sentence is read as a name: "We thanked Rose".
        return False
    # Re-tag the sentence with the word lower-cased. "However", "Timescale" and "Game"
    # become ordinary words; "Sarah" and "David" stay proper nouns and are kept.
    sent = tok.sent
    offset = tok.idx - sent.start_char
    lowered = sent.text[:offset] + low + sent.text[offset + len(word) :]
    retagged = nlp(lowered)
    match = retagged.char_span(offset, offset + len(word), alignment_mode="expand")
    return match is not None and match[0].pos_ != "PROPN"


def refine_person(
    text: str, start: int, end: int, doc: Doc, nlp: Language, cued: bool
) -> tuple[int, int] | None:
    """Trim a PERSON span to its name, or return None if nothing in it is a name."""
    words = [(m.start() + start, m.end() + start) for m in re.finditer(r"\S+", text[start:end])]
    # Strip punctuation around each word so "Dad," is checked as "Dad".
    words = [_strip_punct(text, s, e) for s, e in words]
    words = [(s, e) for s, e in words if s < e]
    while words and _never_a_name(text[words[0][0] : words[0][1]], _after_role(text, words[0][0])):
        words.pop(0)
    while words and _never_a_name(text[words[-1][0] : words[-1][1]], _after_role(text, words[-1][0])):
        words.pop()
    if not words:
        return None
    new_start, new_end = words[0][0], words[-1][1]
    # A word straight after "nurse" or "my son" counts as cued even in lower case.
    cued = cued or _after_role(text, new_start)
    if len(words) == 1 and not cued and _ordinary_word_in_context(doc, new_start, new_end, nlp):
        return None
    return new_start, new_end


def _after_role(text: str, start: int) -> bool:
    """True when the word before `start` is a role or kinship word ("nurse", "my son")."""
    before = re.search(r"(\S+)\s+$", text[:start])
    return before is not None and _is_kinship_or_role(before.group(1).strip(".,"))


def _strip_punct(text: str, s: int, e: int) -> tuple[int, int]:
    while s < e and not (text[s].isalnum()):
        s += 1
    while e > s and not (text[e - 1].isalnum() or text[e - 1] in "'’"):
        e -= 1
    return s, e
