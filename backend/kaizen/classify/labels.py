"""The four labels every comment gets (FR3), from docs/labelling-guide.md.

The definitions here are what the model is told, so keep them in step with the guide.
Changing any text in this file changes `PROMPT_VERSION`, which is stored with each label.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, field_validator


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Category(str, enum.Enum):
    QUALITY = "quality"
    SAFETY = "safety"
    ENVIRONMENT = "environment"
    INSTITUTIONAL_PROCESSES = "institutional_processes"
    LISTENING = "listening"
    COMMUNICATION = "communication"
    RESPECT_AND_RIGHTS = "respect_and_rights"


class Stage(str, enum.Enum):
    ADMISSIONS = "admissions"
    EXAMINATION_AND_DIAGNOSIS = "examination_and_diagnosis"
    CARE_ON_THE_WARD = "care_on_the_ward"
    OPERATIONS_AND_PROCEDURES = "operations_and_procedures"
    DISCHARGE_AND_TRANSFERS = "discharge_and_transfers"
    UNCLEAR = "unclear"


class Urgency(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Labels(BaseModel):
    sentiment: Sentiment
    categories: list[Category]
    stage: Stage
    urgency: Urgency

    @field_validator("categories")
    @classmethod
    def _no_repeats(cls, value: list[Category]) -> list[Category]:
        return list(dict.fromkeys(value))

    def as_dict(self) -> dict:
        return {
            "sentiment": self.sentiment.value,
            "categories": sorted(c.value for c in self.categories),
            "stage": self.stage.value,
            "urgency": self.urgency.value,
        }


SENTIMENT_RULES = {
    Sentiment.POSITIVE: "mainly praise or thanks",
    Sentiment.NEUTRAL: "a suggestion, a question, or a plain report with no clear feeling",
    Sentiment.NEGATIVE: "mainly a complaint or something going wrong",
}

CATEGORY_RULES = {
    Category.QUALITY: "the standard of clinical or nursing care: rushed or careless care, poor pain control, basic needs not met",
    Category.SAFETY: "errors, near misses and risk of harm: wrong or missed medication, falls, misdiagnosis, staff not acting when they should",
    Category.ENVIRONMENT: "the building and resources: cleanliness, noise, food, beds, equipment, parking, not enough staff on shift",
    Category.INSTITUTIONAL_PROCESSES: "how the hospital runs: waiting times, delays, admission and discharge processes, paperwork, referrals, bed management",
    Category.LISTENING: "concerns ignored or dismissed: patient or family not believed, pain brushed off, a staff concern not acted on",
    Category.COMMUNICATION: "information that is unclear, wrong, missing or inconsistent: explanations, discharge instructions, results not passed on, handover gaps",
    Category.RESPECT_AND_RIGHTS: "rudeness, lack of dignity or privacy, consent, discrimination",
}

STAGE_RULES = {
    Stage.ADMISSIONS: "arriving and being admitted: ED waits, triage, waiting for a bed",
    Stage.EXAMINATION_AND_DIAGNOSIS: "assessment, tests, scans, results and diagnosis",
    Stage.CARE_ON_THE_WARD: "day to day care during the stay: nursing, medication rounds, food, the room, visiting",
    Stage.OPERATIONS_AND_PROCEDURES: "surgery, procedures, anaesthesia and recovery straight after",
    Stage.DISCHARGE_AND_TRANSFERS: "going home or moving between units or hospitals: discharge planning, instructions, take-home prescriptions, transport",
    Stage.UNCLEAR: "the comment does not say, or it is about the hospital in general",
}

URGENCY_RULES = {
    Urgency.LOW: "an inconvenience or minor problem with no harm; praise is always low",
    Urgency.MEDIUM: "the writer was distressed, care was delayed, or the problem will likely happen again unless someone looks at it",
    Urgency.HIGH: "harm or a real risk of harm: medication error, fall, abuse, missed deterioration, unsafe discharge",
}

CLOSE_CALLS = [
    "When a comment mixes praise and a complaint, choose the sentiment the writer spends more words on; if even, choose negative.",
    "A comment that only praises gets no problem categories.",
    "A wait on its own is institutional_processes. Add communication only if the comment says nobody explained the wait.",
    "Short staffing is environment. If it led to harm or a near miss, add safety.",
    "Medication given late is quality. The wrong drug or dose, or a missed dose, is safety.",
    "If a comment covers several stages, choose the stage the main problem is in.",
    "When unsure between two urgency levels, choose the higher one.",
]

EXAMPLES = [
    (
        "patient_family",
        "The surgeon was great but I waited 9 hours in ED with no update.",
        Labels(
            sentiment=Sentiment.NEGATIVE,
            categories=[Category.INSTITUTIONAL_PROCESSES, Category.COMMUNICATION],
            stage=Stage.ADMISSIONS,
            urgency=Urgency.MEDIUM,
        ),
    ),
    (
        "patient_family",
        "We were sent home with no instructions about the new blood thinner.",
        Labels(
            sentiment=Sentiment.NEGATIVE,
            categories=[Category.COMMUNICATION, Category.SAFETY],
            stage=Stage.DISCHARGE_AND_TRANSFERS,
            urgency=Urgency.HIGH,
        ),
    ),
    (
        "staff",
        "Night shift handed over two patients without telling us about their falls risk.",
        Labels(
            sentiment=Sentiment.NEGATIVE,
            categories=[Category.COMMUNICATION, Category.SAFETY],
            stage=Stage.CARE_ON_THE_WARD,
            urgency=Urgency.HIGH,
        ),
    ),
    (
        "patient_family",
        "The nurses on 4B were lovely and always came when I rang.",
        Labels(sentiment=Sentiment.POSITIVE, categories=[], stage=Stage.CARE_ON_THE_WARD, urgency=Urgency.LOW),
    ),
]
