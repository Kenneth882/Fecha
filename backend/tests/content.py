"""A fake content generator for tests, so no test calls a real LLM."""

from decimal import Decimal

from app.services.catalog import Scenario
from app.services.content_generator import Generation
from app.services.listen_content import ListenDialogueContent
from app.services.planner import Level
from app.services.vocab_content import VocabItemsContent
from tests.unit.test_listen_dialogue_content import dialogue


class FakeGenerator:
    """Returns valid content for every call, or raises for the Scenarios in `failing`.
    Records each Listen Dialogue call's (language, Scenario slug, Level) in `calls`, and
    each Vocab Items call's (language, Scenario slug, Level, count, existing phrases) in
    `vocab_calls`. Vocab phrases are `vocab_phrases` if given, else "{slug} {level} {n}"."""

    def __init__(
        self,
        *,
        failing: set[str] | None = None,
        cost_usd: Decimal = Decimal("0.01"),
        vocab_phrases: list[str] | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, Level]] = []
        self.vocab_calls: list[tuple[str, str, Level, int, list[str]]] = []
        self.failing = failing or set()
        self.cost_usd = cost_usd
        self.vocab_phrases = vocab_phrases

    async def listen_dialogue(
        self, language: str, scenario: Scenario, level: Level
    ) -> Generation[ListenDialogueContent]:
        self.calls.append((language, scenario.slug, level))
        if scenario.slug in self.failing:
            raise RuntimeError("the LLM said no")
        return Generation(
            content=ListenDialogueContent.model_validate(dialogue()),
            model="fake-model",
            input_tokens=100,
            output_tokens=200,
            cost_usd=self.cost_usd,
        )

    async def vocab_items(
        self,
        language: str,
        scenario: Scenario,
        level: Level,
        count: int,
        existing_phrases: list[str],
    ) -> Generation[VocabItemsContent]:
        self.vocab_calls.append((language, scenario.slug, level, count, existing_phrases))
        if scenario.slug in self.failing:
            raise RuntimeError("the LLM said no")
        phrases = self.vocab_phrases or [f"{scenario.slug} {level} {n}" for n in range(count)]
        return Generation(
            content=VocabItemsContent.model_validate(
                {"items": [{"phrase": p, "translation": f"{p} (en)"} for p in phrases]},
                context={"count": count},
            ),
            model="fake-model",
            input_tokens=100,
            output_tokens=200,
            cost_usd=self.cost_usd,
        )
