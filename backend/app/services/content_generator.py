"""The content generator: the one thing that asks an LLM for content.

One method per content kind, each taking a (language, Scenario, Level) key and
returning validated content with what the call cost. The worker's composition root
picks the implementation: `OffContentGenerator` when there's no API key, the real one
(instructor and the Anthropic SDK) from #70, and a fake in tests. Pure: no I/O here.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.services.catalog import Scenario
from app.services.listen_content import ListenDialogueContent
from app.services.planner import Level


@dataclass(frozen=True)
class Generation[T]:
    """Content from one call, already validated, and what the call used."""

    content: T
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class GenerationSkippedError(Exception):
    """The generator made no call: generation is off because there's no API key."""


class GenerationFailedError(Exception):
    """A call was made but produced no usable content, even after its retries.

    Carries what the failed call used, so its cost still counts against the budget.
    """

    def __init__(
        self,
        message: str,
        *,
        model: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: Decimal = Decimal(0),
    ) -> None:
        super().__init__(message)
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd


class ContentGenerator(Protocol):
    """Generates content for a (language, Scenario, Level) key.

    Raises GenerationSkippedError if it made no call, and GenerationFailedError (or any
    other exception) if the call failed; either way the caller falls back.
    """

    async def listen_dialogue(
        self, language: str, scenario: Scenario, level: Level
    ) -> Generation[ListenDialogueContent]:
        """One Listen Dialogue in `language` for the Scenario, suited to the Level."""
        ...


class OffContentGenerator:
    """Generation is off (no API key): every call is skipped, and Users keep getting
    the hand-written fallbacks."""

    async def listen_dialogue(
        self, language: str, scenario: Scenario, level: Level
    ) -> Generation[ListenDialogueContent]:
        raise GenerationSkippedError("content generation is off: ANTHROPIC_API_KEY is not set")
