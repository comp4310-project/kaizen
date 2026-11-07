"""Our own Presidio recognizers for details the built-in ones miss or over-match.

Presidio's spaCy date recognizer also tags lengths of time ("waited 3 days"), which our
classifier needs, so calendar dates are matched by pattern instead. Ontario health card
and record numbers have no built-in recognizer at all.
"""

from __future__ import annotations

import re

from presidio_analyzer import EntityRecognizer, Pattern, PatternRecognizer, RecognizerResult

# Presidio's default flags include IGNORECASE. Month names use it too, except "May",
# which is only a date when capitalised ("May 3", not "may 3 of them").
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|(?-i:May)|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s+\d{4}\b)?"


def luhn_valid(digits: str) -> bool:
    """Ontario health numbers end in a Luhn check digit."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class CalendarDateRecognizer(PatternRecognizer):
    """Dates that point to a day: "March 3", "3rd of November", "03/11/2026", "2026-11-03".

    Lengths of time, times of day, weekdays, months on their own and years on their own
    are left alone. Numeric dates need a year, so "8/10" pain scores are not dates.
    """

    PATTERNS = [
        Pattern("month day", rf"\b{_MONTH}\.?\s+{_DAY}\b{_YEAR}", 0.6),
        Pattern("day month", rf"\b{_DAY}\s+(?:of\s+)?{_MONTH}\b\.?{_YEAR}", 0.6),
        # The lookahead allows a full stop after the date but not "3/4/25.5" or "3/4/25/1".
        Pattern("numeric", r"(?<![\d/.-])\d{1,2}[/.-]\d{1,2}[/.-](?:\d{4}|\d{2})(?![\d/-]|\.\d)", 0.6),
        Pattern("iso", r"(?<![\d-])\d{4}-\d{1,2}-\d{1,2}(?![\d-]|\.\d)", 0.6),
    ]

    def __init__(self) -> None:
        super().__init__(supported_entity="DATE", patterns=self.PATTERNS, name="CalendarDateRecognizer")


class HealthCardRecognizer(PatternRecognizer):
    """Ontario health card numbers: 10 digits, often 4-3-3, sometimes with a 2-letter version code.

    A valid check digit raises the score, but an invalid one is still removed, since a
    mistyped health number is still personal.
    """

    PATTERNS = [
        Pattern(
            "ontario hcn",
            r"(?<![\d-])\d{4}[- ]?\d{3}[- ]?\d{3}(?:[- ]?[A-Z]{2})?(?![\w-])",
            0.5,
        ),
    ]
    CONTEXT = ["health", "card", "ohip", "hcn", "number"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="HEALTH_CARD",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            name="HealthCardRecognizer",
        )

    def validate_result(self, pattern_text: str) -> bool | None:
        digits = re.sub(r"\D", "", pattern_text)
        if len(digits) == 10 and luhn_valid(digits):
            return True
        return None  # keep the pattern score rather than dropping it


class RecordNumberRecognizer(PatternRecognizer):
    """Hospital record (chart, MRN) numbers: 6 to 9 digits, with up to 3 letters in front.

    Feedback rarely has any other number this long, so a bare one is removed even without
    "MRN" or "chart" next to it.
    """

    PATTERNS = [Pattern("record number", r"(?<![\w-])[A-Z]{0,3}-?\d{6,9}(?![\w-])", 0.5)]
    CONTEXT = ["mrn", "chart", "record", "file", "patient", "number"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="RECORD_NUMBER",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            name="RecordNumberRecognizer",
        )


class PhonePatternRecognizer(PatternRecognizer):
    """North American phone numbers in the usual formats.

    Backs up Presidio's PhoneRecognizer, which rejects numbers it considers invalid, such
    as the fictional 555-01xx numbers our synthetic data uses.
    """

    PATTERNS = [
        Pattern(
            "nanp",
            r"(?<![\w-])(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}(?![\w-])",
            0.6,
        ),
    ]

    def __init__(self) -> None:
        super().__init__(supported_entity="PHONE_NUMBER", patterns=self.PATTERNS, name="PhonePatternRecognizer")


_NAME = r"([A-Z][a-z'\u2019]+(?:-[A-Z][a-z]+)?(?:\s+[A-Z][a-z'\u2019]+(?:-[A-Z][a-z]+)?)?)"

# Capitalised words that a cue can pick up but are not names ("Nurse Practitioner",
# "Thanks from the night shift").
_NOT_NAMES = {
    "Practitioner", "Manager", "Educator", "Supervisor", "Station", "Team", "Staff", "Everyone",
    "Nobody", "Someone", "Nurses", "Doctors", "Thanks", "Thank", "Please", "Patient", "Pt",
    "Call", "Email", "Phone", "Text", "Contact", "Chart",
    "The", "On", "In", "At", "And", "Who", "Was", "Is", "This", "That", "We", "They", "She", "He",
}
_PHONE_OR_EMAIL_AHEAD = r"(?=(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b|\S+@\S+)"


class CuedNameRecognizer(EntityRecognizer):
    """Names that follow a cue spaCy often misses: "nurse Rose", "Dr Bird", "my daughter Grace",
    a sign-off ("- Grace Little" at the end), a name before contact details, or a name
    before a shift ("Faith from nights").

    Only the name is tagged, so "Dr. Patel" becomes "Dr. <PERSON>" and the role stays
    readable. Names written in lower case are not caught.
    """

    CUES = [
        re.compile(r"(?i:\b(?:dr\.?|doctor|nurse|mr\.?|mrs\.?|ms\.?|miss))\s+" + _NAME),
        re.compile(
            r"(?i:\b(?:my|our|his|her|their)\s+(?:wife|husband|partner|son|daughter|mother|mom|mum"
            r"|father|dad|sister|brother|grandson|granddaughter|grandmother|grandma|grandfather"
            r"|grandpa|aunt|uncle|friend|niece|nephew|roommate|neighbour|neighbor)),?\s+" + _NAME
        ),
        re.compile(r"(?i:\b(?:named|called|name is|name's|signed|regards|sincerely))[,:]?\s+" + _NAME),
        re.compile(_NAME + r",?\s+(?:RN|RPN|NP|MD)\b"),
        re.compile(r"(?:^|\s)-\s*" + _NAME + r"\s*$"),
        re.compile(r"(?:^|[.!?]\s+)" + _NAME + r",\s*" + _PHONE_OR_EMAIL_AHEAD),
        re.compile(_NAME + r"\s+(?i:(?:from|on)\s+(?:the\s+)?(?:nights?|days?|evenings?)\b)"),
    ]

    def __init__(self) -> None:
        super().__init__(supported_entities=["PERSON"], name="CuedNameRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text, entities, nlp_artifacts=None):  # noqa: ANN001 (Presidio signature)
        results = []
        for pattern in self.CUES:
            for m in pattern.finditer(text):
                start, end = m.span(1)
                words = m.group(1).split()
                if words[0] in _NOT_NAMES:
                    continue
                if len(words) > 1 and words[1] in _NOT_NAMES:
                    end = start + len(words[0])
                results.append(RecognizerResult("PERSON", start, end, 0.7))
        return results
