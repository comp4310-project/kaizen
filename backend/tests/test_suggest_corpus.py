"""Loading the documents behind suggestions and cutting them into passages (FR7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kaizen.suggest.corpus import MAX_PASSAGE_WORDS, CorpusError, Document, load_corpus, split_passages

POLICY = """---
title: Discharge medication reconciliation
source: Sample policy written by the Kaizen team
kind: sample_policy
---

# Purpose

Patients leave with an accurate list of the medications they should take at home.

# Procedure

## Before discharge

The most responsible nurse reviews every new medication with the patient and family.

The pharmacist checks the home medication list against the discharge prescription.

## After discharge

A follow-up call is made within 48 hours for patients on high-alert medications.
"""


def write(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_front_matter_and_uses_the_file_name_as_id(tmp_path) -> None:
    write(tmp_path, "discharge-meds-policy.md", POLICY)
    (doc,) = load_corpus(tmp_path)
    assert doc.id == "discharge-meds-policy"
    assert doc.title == "Discharge medication reconciliation"
    assert doc.kind == "sample_policy"
    assert doc.url is None
    assert doc.body.startswith("# Purpose")


def test_documents_load_in_file_name_order(tmp_path) -> None:
    write(tmp_path, "b.md", POLICY)
    write(tmp_path, "a.md", POLICY)
    write(tmp_path, "notes.txt", "not a document")
    assert [d.id for d in load_corpus(tmp_path)] == ["a", "b"]


@pytest.mark.parametrize(
    "text, problem",
    [
        ("# No front matter\n\nText.", "front matter"),
        ("---\ntitle: T\nsource: S\n---\nText.", "kind"),
        ("---\ntitle: T\nsource: S\nkind: blog_post\n---\nText.", "kind"),
        ("---\ntitle: T\nsource: S\nkind: sample_policy\n---\n\n", "no text"),
    ],
)
def test_bad_documents_are_reported_with_their_file(tmp_path, text, problem) -> None:
    write(tmp_path, "bad.md", text)
    with pytest.raises(CorpusError, match="bad.md") as error:
        load_corpus(tmp_path)
    assert problem in str(error.value)


def test_passages_keep_their_section_and_never_cross_a_heading() -> None:
    doc = Document(id="p", title="T", source="S", kind="sample_policy", url=None, body=POLICY.split("---\n", 2)[2])
    passages = split_passages(doc)

    assert [p.id for p in passages] == ["p:0", "p:1", "p:2"]
    assert [p.heading for p in passages] == ["Purpose", "Procedure > Before discharge", "Procedure > After discharge"]
    # Both paragraphs under "Before discharge" fit in one passage.
    assert "reviews every new medication" in passages[1].text
    assert "pharmacist checks" in passages[1].text
    assert all("#" not in p.text for p in passages)


def test_long_sections_are_cut_at_sentence_ends() -> None:
    sentence = "Each unit keeps a written record of every discharge call it makes. "
    body = "# Calls\n\n" + sentence * 60
    doc = Document(id="long", title="T", source="S", kind="sample_policy", url=None, body=body)
    passages = split_passages(doc)

    assert len(passages) > 1
    assert all(len(p.text.split()) <= MAX_PASSAGE_WORDS for p in passages)
    assert all(p.text.endswith("makes.") for p in passages)
    assert " ".join(p.text for p in passages).split() == body.split("\n\n", 1)[1].split()


def test_one_overlong_sentence_becomes_its_own_passage() -> None:
    # Cutting mid-sentence would let a quote straddle two passages, so a sentence is never split.
    long_sentence = " ".join(["word"] * (MAX_PASSAGE_WORDS + 20)) + "."
    doc = Document(id="x", title="T", source="S", kind="sample_policy", url=None, body=f"Short one. {long_sentence} Short two.")
    passages = split_passages(doc)
    assert [len(p.text.split()) for p in passages] == [2, MAX_PASSAGE_WORDS + 20, 2]


def test_search_text_includes_title_and_section() -> None:
    doc = Document(id="p", title="Discharge policy", source="S", kind="sample_policy", url=None, body="# Calls\n\nCall within 48 hours.")
    (passage,) = split_passages(doc)
    assert passage.search_text == "Discharge policy. Calls. Call within 48 hours."


def test_missing_folder_is_an_error_not_an_empty_corpus(tmp_path) -> None:
    with pytest.raises(CorpusError, match="no such folder"):
        load_corpus(tmp_path / "documents")
