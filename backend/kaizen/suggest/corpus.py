"""The documents suggestions are drawn from, cut into passages small enough to search and quote.

P3 plans 30-50 documents: Ontario quality standards, QIP guidance and sample hospital
policies we write ourselves. Each is a Markdown file whose name is its id, starting with a
short header:

    ---
    title: Discharge medication reconciliation
    source: Sample policy written by the Kaizen team
    kind: sample_policy
    url: https://...            (optional)
    ---

    # Section heading

    Text...

A passage is a run of whole sentences from one section, so a quote never spans a heading and
the heading can be shown next to the citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

KINDS = ("quality_standard", "qip_guidance", "sample_policy")

# all-MiniLM-L6-v2 reads at most 256 word pieces. 150 words leaves room for the title and
# section that are searched along with the text.
MAX_PASSAGE_WORDS = 150

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class CorpusError(ValueError):
    pass


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    source: str
    kind: str
    url: str | None
    body: str


@dataclass(frozen=True)
class Passage:
    id: str  # "<document id>:<n>", stable as long as the document text is unchanged
    document_id: str
    title: str
    heading: str  # "Procedure > Before discharge", or "" before the first heading
    text: str

    @property
    def search_text(self) -> str:
        return ". ".join(part for part in (self.title, self.heading, self.text) if part)


def load_corpus(folder: Path) -> list[Document]:
    return [_read(path) for path in sorted(Path(folder).glob("*.md"))]


def _read(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[3:]:
        raise CorpusError(f"{path.name}: no front matter, it must start with a --- header")
    header, body = text[4:].split("\n---\n", 1)
    fields = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep and value.strip():
            fields[key.strip()] = value.strip()

    for required in ("title", "source", "kind"):
        if required not in fields:
            raise CorpusError(f"{path.name}: missing {required}")
    if fields["kind"] not in KINDS:
        raise CorpusError(f"{path.name}: unknown kind {fields['kind']!r}, use one of {', '.join(KINDS)}")
    if not body.strip():
        raise CorpusError(f"{path.name}: no text after the header")

    return Document(
        id=path.stem,
        title=fields["title"],
        source=fields["source"],
        kind=fields["kind"],
        url=fields.get("url"),
        body=body.strip(),
    )


def split_passages(doc: Document, max_words: int = MAX_PASSAGE_WORDS) -> list[Passage]:
    passages: list[Passage] = []
    for heading, paragraphs in _sections(doc.body):
        for text in _pack(paragraphs, max_words):
            passages.append(Passage(f"{doc.id}:{len(passages)}", doc.id, doc.title, heading, text))
    return passages


def _sections(body: str) -> list[tuple[str, list[str]]]:
    """(heading path, paragraphs) for every section that has text."""
    sections: list[tuple[str, list[str]]] = []
    path: list[str] = []
    paragraphs: list[str] = []
    current: list[str] = []

    def end_paragraph() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    def end_section() -> None:
        end_paragraph()
        if paragraphs:
            sections.append((" > ".join(path), paragraphs.copy()))
            paragraphs.clear()

    for line in body.splitlines():
        heading = _HEADING.match(line)
        if heading:
            end_section()
            level = len(heading.group(1))
            path[:] = path[: level - 1] + [heading.group(2)]
        elif line.strip():
            current.append(line.strip())
        else:
            end_paragraph()
    end_section()
    return sections


def _pack(paragraphs: list[str], max_words: int) -> list[str]:
    """Fills passages with whole sentences, up to max_words each.

    A sentence longer than max_words gets a passage of its own rather than being cut, since a
    quote that straddled two passages would fail the citation check.
    """
    passages: list[str] = []
    text = ""
    count = 0
    for n, paragraph in enumerate(paragraphs):
        for i, sentence in enumerate(_SENTENCE_END.split(paragraph)):
            size = len(sentence.split())
            if text and count + size > max_words:
                passages.append(text)
                text, count = "", 0
            joiner = "\n\n" if i == 0 and n > 0 else " "
            text = f"{text}{joiner}{sentence}" if text else sentence
            count += size
            if count > max_words:
                passages.append(text)
                text, count = "", 0
    if text:
        passages.append(text)
    return passages
