"""Labels comments with Claude (FR3). Only de-identified comment text is ever sent (NFR1).

Needs ANTHROPIC_API_KEY. The model and effort can be changed with KAIZEN_LABEL_MODEL and
KAIZEN_LABEL_EFFORT, and both are stored with every label so results can be traced (NFR5).
P3 plans a low-cost model for bulk labelling, so the default is Claude Haiku 5.5 at low
effort.
"""

from __future__ import annotations

import os
from typing import Sequence

import anthropic
from pydantic import BaseModel, ValidationError

from kaizen.classify.labels import Category, Labels, Sentiment, Stage, Urgency
from kaizen.classify.prompt import BATCH_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT, CommentInput, render_batch

DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_EFFORT = "low"
# Room for adaptive thinking plus about 80 tokens of JSON per comment.
MAX_TOKENS = 8000


class LabelError(RuntimeError):
    """One batch could not be labelled. Its comments stay unlabelled and are retried next run."""


class _Item(BaseModel):
    id: int
    sentiment: Sentiment
    categories: list[Category]
    stage: Stage
    urgency: Urgency


class _Batch(BaseModel):
    labels: list[_Item]


class ClaudeLabeller:
    def __init__(self, client=None, model: str | None = None, effort: str | None = None) -> None:
        # The SDK already retries 429s, 5xx and dropped connections; give it a few more tries
        # since a run sends hundreds of requests.
        self.client = client or anthropic.Anthropic(max_retries=4)
        self.model = model or os.environ.get("KAIZEN_LABEL_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("KAIZEN_LABEL_EFFORT", DEFAULT_EFFORT)

    @property
    def name(self) -> str:
        return f"{self.model}/{self.effort}"

    @property
    def version(self) -> str:
        return PROMPT_VERSION

    def label(self, items: Sequence[CommentInput]) -> dict[int, Labels]:
        """Labels for each id Claude returned. Ids it skipped are simply missing."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                # Same text on every request, so it is cached after the first one.
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": render_batch(list(items))}],
                output_config={
                    "format": {"type": "json_schema", "schema": BATCH_SCHEMA},
                    "effort": self.effort,
                },
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.BadRequestError, anthropic.NotFoundError):
            raise  # a wrong key, model name or request: every batch would fail, so stop the run
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise LabelError(f"API error after retries: {type(exc).__name__}") from exc

        if response.stop_reason == "refusal":
            raise LabelError("model declined the batch")
        if response.stop_reason == "max_tokens":
            raise LabelError("reply was cut off, use a smaller batch")
        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            raise LabelError("reply had no text block")
        try:
            batch = _Batch.model_validate_json(text)
        except ValidationError as exc:
            raise LabelError("reply did not match the label schema") from exc

        wanted = {item.id for item in items}
        return {
            item.id: Labels(sentiment=item.sentiment, categories=item.categories, stage=item.stage, urgency=item.urgency)
            for item in batch.labels
            if item.id in wanted
        }
