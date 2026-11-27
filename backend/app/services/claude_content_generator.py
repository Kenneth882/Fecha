"""The real content generator: Claude, through instructor and the Anthropic SDK.

A thin wrapper. The prompts live in `listen_prompts` and `vocab_prompts`, the response
checks are validators on `ListenDialogueContent` and `VocabItemsContent`, and the prices
live in `llm_prices`, all pure; the checks and the prices are unit-tested. This module
only makes the call, so tests never use it (they use a fake `ContentGenerator`). The
worker's composition root builds it when ANTHROPIC_API_KEY is set, with the Anthropic
client it opens at startup and closes at shutdown.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import instructor
from anthropic import AsyncAnthropic
from anthropic.types import Usage
from pydantic import BaseModel

from app.services.catalog import Scenario
from app.services.content_generator import Generation, GenerationFailedError
from app.services.listen_content import ListenDialogueContent
from app.services.listen_prompts import Prompt, listen_dialogue_prompt
from app.services.llm_prices import call_cost_usd, require_price
from app.services.planner import Level
from app.services.vocab_content import VocabItemsContent
from app.services.vocab_prompts import vocab_items_prompt

# A response that fails the checks is sent back with what failed, at most this many
# times, before the generator gives up and the Task keeps its hand-written fallback.
# instructor makes `VALIDATION_RETRIES + 1` attempts in all.
VALIDATION_RETRIES = 2
# A dialogue and its questions, or ten Vocab Items, are about 1-2K output tokens; the
# rest leaves room for the model's thinking, so a response is never cut off.
MAX_TOKENS = 16_000


class ClaudeContentGenerator:
    """Generates content with a Claude model, using structured outputs."""

    def __init__(self, client: AsyncAnthropic, model: str) -> None:
        # Fail at startup, not on every call, if the model can't be costed.
        require_price(model)
        self._client = instructor.from_anthropic(client, mode=instructor.Mode.JSON_SCHEMA)
        self._model = model

    async def listen_dialogue(
        self, language: str, scenario: Scenario, level: Level
    ) -> Generation[ListenDialogueContent]:
        return await self._generate(
            listen_dialogue_prompt(language, scenario, level),
            ListenDialogueContent,
            "Listen Dialogue",
        )

    async def vocab_items(
        self,
        language: str,
        scenario: Scenario,
        level: Level,
        count: int,
        existing_phrases: list[str],
    ) -> Generation[VocabItemsContent]:
        return await self._generate(
            vocab_items_prompt(language, scenario, level, count, existing_phrases),
            VocabItemsContent,
            "Vocab Items",
            context={"count": count},
        )

    async def _generate[T: BaseModel](
        self,
        prompt: Prompt,
        response_model: type[T],
        what: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> Generation[T]:
        """One structured call for `response_model`, whose validators get `context`."""
        try:
            content, completion = await self._client.create_with_completion(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=prompt.system,
                messages=[{"role": "user", "content": prompt.user}],
                response_model=response_model,
                max_retries=VALIDATION_RETRIES,
                context=context,
            )
        except instructor.InstructorRetryException as exc:
            raise self._failed(
                f"no valid {what} after {exc.n_attempts} attempts: {exc}",
                exc.total_usage,
            ) from exc
        except instructor.IncompleteOutputException as exc:
            # Cut off at MAX_TOKENS. instructor doesn't retry this or wrap it, but the
            # completion it carries already holds every attempt's usage.
            raise self._failed(
                f"the {what} was cut off at max_tokens",
                getattr(exc.last_completion, "usage", None),
            ) from exc
        # instructor adds every attempt's usage onto the completion it returns, so a
        # response that needed a retry is charged for every call.
        usage = self._usage(completion.usage)
        return Generation(
            content=content,
            model=self._model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        )

    def _failed(self, message: str, usage: Any) -> GenerationFailedError:
        """A failure that still carries what its attempts used, so it counts toward the
        daily cap."""
        used = self._usage(usage)
        return GenerationFailedError(
            message,
            model=self._model,
            input_tokens=used.input_tokens,
            output_tokens=used.output_tokens,
            cost_usd=used.cost_usd,
        )

    def _usage(self, usage: Any) -> "_Usage":
        """The tokens an Anthropic usage reports (none if there's no usage) and their cost."""
        if not isinstance(usage, Usage):
            return _Usage(0, 0, Decimal(0))
        return _Usage(
            usage.input_tokens,
            usage.output_tokens,
            call_cost_usd(self._model, usage.input_tokens, usage.output_tokens),
        )


@dataclass(frozen=True)
class _Usage:
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
