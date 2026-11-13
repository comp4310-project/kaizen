"""Labels comments with an LLM through LiteLLM (FR3). Only de-identified text is ever sent (NFR1).

LiteLLM lets us change provider, or move to a local model, by changing the model name
(P3 section 4). The default is Claude Haiku 5.5 at low effort, since P3 plans a low-cost
model for bulk labelling; it needs ANTHROPIC_API_KEY. KAIZEN_LABEL_MODEL and
KAIZEN_LABEL_EFFORT change the model and effort, and both are stored with every label so
results can be traced (NFR5).
"""

from __future__ import annotations

import os
from typing import Callable, Sequence

import litellm
from pydantic import BaseModel, ValidationError

from kaizen.classify.labels import Category, Labels, Sentiment, Stage, Urgency
from kaizen.classify.prompt import BATCH_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT, CommentInput, render_batch

DEFAULT_MODEL = "anthropic/claude-haiku-5-5"
DEFAULT_EFFORT = "low"
# Room for thinking plus about 80 tokens of JSON per comment.
MAX_TOKENS = 8000
# LiteLLM retries rate limits, server errors and dropped connections; a run sends hundreds
# of requests, so allow a few tries.
RETRIES = 4

# A wrong key, model name or request: every batch would fail the same way, so stop the run.
CONFIG_ERRORS = (litellm.AuthenticationError, litellm.PermissionDeniedError, litellm.BadRequestError, litellm.NotFoundError)
# Still failing after the retries: give up on this batch only.
SERVICE_ERRORS = (
    litellm.RateLimitError,
    litellm.APIConnectionError,
    litellm.Timeout,
    litellm.InternalServerError,
    litellm.ServiceUnavailableError,
    litellm.APIError,
)

RESPONSE_FORMAT = {"type": "json_schema", "json_schema": {"name": "labels", "schema": BATCH_SCHEMA, "strict": True}}


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


def reply_text(completion: Callable, **kwargs) -> str:
    """Send one request and return the reply text, or raise LabelError. Shared with the issue namer."""
    try:
        response = completion(num_retries=RETRIES, **kwargs)
    except CONFIG_ERRORS:
        raise
    except SERVICE_ERRORS as exc:
        raise LabelError(f"API error after retries: {type(exc).__name__}") from exc

    choice = response.choices[0]
    if choice.finish_reason == "content_filter":
        raise LabelError("model declined the request")
    if choice.finish_reason == "length":
        raise LabelError("reply was cut off")
    if not choice.message.content:
        raise LabelError("reply had no text")
    return choice.message.content


class LLMLabeller:
    def __init__(self, completion: Callable | None = None, model: str | None = None, effort: str | None = None) -> None:
        # Tests pass a fake in place of litellm.completion.
        self.completion = completion or litellm.completion
        self.model = model or os.environ.get("KAIZEN_LABEL_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("KAIZEN_LABEL_EFFORT", DEFAULT_EFFORT)

    @property
    def name(self) -> str:
        return f"{self.model}/{self.effort}"

    @property
    def version(self) -> str:
        return PROMPT_VERSION

    def label(self, items: Sequence[CommentInput]) -> dict[int, Labels]:
        """Labels for each id the model returned. Ids it skipped are simply missing."""
        text = reply_text(
            self.completion,
            model=self.model,
            max_tokens=MAX_TOKENS,
            messages=[
                # Same text on every request, so providers that cache prompts only charge for it once.
                {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]},
                {"role": "user", "content": render_batch(list(items))},
            ],
            response_format=RESPONSE_FORMAT,
            reasoning_effort=self.effort,
        )
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
