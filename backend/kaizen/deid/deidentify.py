"""Replace personal details in a comment with tags such as <PERSON> (FR2, NFR1).

This is the only code that sees original text. Callers must store or forward only
`DeidResult.text`, never the input.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import EmailRecognizer, PhoneRecognizer, SpacyRecognizer

from kaizen.deid.recognizers import (
    CalendarDateRecognizer,
    CuedNameRecognizer,
    HealthCardRecognizer,
    PhonePatternRecognizer,
    RecordNumberRecognizer,
)
from kaizen.units import unit_mention_pattern

DEFAULT_MODEL = "en_core_web_lg"
SCORE_THRESHOLD = 0.4

# Presidio entity name -> tag written into the text.
TAGS = {
    "PERSON": "PERSON",
    "DATE": "DATE",
    "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
    "HEALTH_CARD": "HEALTH_CARD",
    "RECORD_NUMBER": "RECORD_NUMBER",
}


@dataclass(frozen=True)
class Span:
    """Where a detail was found in the original text. Holds no personal text itself."""

    start: int
    end: int
    tag: str
    score: float


@dataclass(frozen=True)
class DeidResult:
    text: str
    spans: tuple[Span, ...]

    @property
    def counts(self) -> dict[str, int]:
        """How many details of each kind were removed. Safe to store and log."""
        return dict(Counter(s.tag for s in self.spans))


@lru_cache(maxsize=2)
def _analyzer(model: str) -> AnalyzerEngine:
    nlp_engine = NlpEngineProvider(
        nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": model}]}
    ).create_engine()
    # Only the recognizers we chose. Presidio's defaults would also remove locations,
    # organisations and spaCy's dates, which takes out unit names and lengths of time.
    registry = RecognizerRegistry(
        recognizers=[
            SpacyRecognizer(supported_entities=["PERSON"]),
            EmailRecognizer(),
            PhoneRecognizer(supported_regions=("CA", "US")),
            PhonePatternRecognizer(),
            CalendarDateRecognizer(),
            HealthCardRecognizer(),
            RecordNumberRecognizer(),
            CuedNameRecognizer(),
        ]
    )
    return AnalyzerEngine(nlp_engine=nlp_engine, registry=registry, supported_languages=["en"])


# Short words spaCy sometimes tags as a person in clinical notes.
_NOT_PERSON = {"pt", "pts", "rn", "rpn", "np", "md", "dr", "er", "ed", "icu", "iv", "prn"}


def _keep(text: str, start: int, end: int, tag: str) -> bool:
    """False for results that are not personal: a unit name, or "Pt" tagged as a person."""
    if tag == "PERSON" and text[start:end].strip(" .").lower() in _NOT_PERSON:
        return False
    return not _inside_unit_name(text, start, end)


def _inside_unit_name(text: str, start: int, end: int) -> bool:
    return any(m.start() <= start and end <= m.end() for m in unit_mention_pattern().finditer(text))


def _merge(spans: list[Span], text: str) -> list[Span]:
    """Merge overlapping spans, and same-tag spans split only by a space ("Rose" "Tremblay")."""
    merged: list[Span] = []
    for span in sorted(spans, key=lambda s: (s.start, -s.end)):
        if merged:
            last = merged[-1]
            gap = text[last.end : span.start]
            if span.start < last.end or (span.tag == last.tag and gap.isspace() and len(gap) <= 2):
                tag = last.tag if last.score >= span.score else span.tag
                merged[-1] = Span(last.start, max(last.end, span.end), tag, max(last.score, span.score))
                continue
        merged.append(span)
    return merged


def find_spans(text: str, model: str | None = None) -> list[Span]:
    model = model or os.environ.get("KAIZEN_SPACY_MODEL", DEFAULT_MODEL)
    results = _analyzer(model).analyze(text=text, language="en", score_threshold=SCORE_THRESHOLD)
    spans = [
        Span(r.start, r.end, TAGS[r.entity_type], r.score)
        for r in results
        if r.entity_type in TAGS and _keep(text, r.start, r.end, TAGS[r.entity_type])
    ]
    return _merge(spans, text)


def deidentify(text: str, model: str | None = None) -> DeidResult:
    spans = find_spans(text, model)
    out = []
    pos = 0
    for span in spans:
        out.append(text[pos : span.start])
        out.append(f"<{span.tag}>")
        pos = span.end
    out.append(text[pos:])
    return DeidResult("".join(out), tuple(spans))
