"""The citation check behind NFR2: a suggestion's quote must appear in the passage it cites."""

from __future__ import annotations

import pytest

from kaizen.suggest.cite import MIN_QUOTE_WORDS, quote_in_passage

PASSAGE = (
    "Before discharge, the most responsible nurse reviews every new medication with the "
    "patient and family, using the teach-back method, and confirms that the prescription "
    "has been sent to the community pharmacy.\n\nFollow-up calls are made within 48 hours "
    "of discharge for patients on high-alert medications."
)


def test_exact_quote_is_found() -> None:
    assert quote_in_passage("reviews every new medication with the patient and family", PASSAGE)


@pytest.mark.parametrize(
    "quote",
    [
        "Reviews Every New Medication with the Patient and Family",  # case
        "reviews  every new\nmedication with the patient and family",  # whitespace and line breaks
        "“reviews every new medication with the patient and family.”",  # curly quotes, full stop
        "using the teach back method, and confirms that",  # hyphen vs space
        "Follow up calls are made within 48 hours",
    ],
)
def test_formatting_differences_do_not_matter(quote: str) -> None:
    assert quote_in_passage(quote, PASSAGE)


def test_word_broken_across_a_line_by_pdf_extraction_still_matches() -> None:
    assert quote_in_passage("confirms that the prescription has been sent", PASSAGE.replace("prescription", "pre-\nscription"))


@pytest.mark.parametrize(
    "quote",
    [
        "reviews every new medication with the patient and pharmacist",  # one word changed
        "reviews every new medication with family",  # words dropped
        "the patient and family, using the teach-back method daily",  # extra word at the end
        "reviews every new medication ... sent to the community pharmacy",  # elided quote
    ],
)
def test_changed_or_stitched_quotes_are_rejected(quote: str) -> None:
    assert not quote_in_passage(quote, PASSAGE)


def test_quote_must_match_whole_words() -> None:
    # "charge" sits inside "discharge"; a substring match would wrongly accept this.
    passage = "Patients are given a discharge summary and a medication list before they leave."
    assert not quote_in_passage("charge summary and a medication list before", passage)


def test_short_quotes_are_rejected_even_when_present() -> None:
    # A few common words appear in almost any passage, so they prove nothing.
    short = " ".join(PASSAGE.split()[: MIN_QUOTE_WORDS - 1])
    assert short.lower() in PASSAGE.lower()
    assert not quote_in_passage(short, PASSAGE)


def test_empty_quote_is_rejected() -> None:
    assert not quote_in_passage("", PASSAGE)
    assert not quote_in_passage("   ", PASSAGE)
