"""The prompt that asks an LLM for a Scenario's generated Vocab Items.

Pure: plain strings built from the Scenario Catalog, the Level and the Scenario's
existing phrases. It shares the Level briefs and the register with the Listen Dialogue
prompt, so both kinds of content sound the same. The Event's free-text goals are never
used (ADR 0008). The response's shape and checks live on `VocabItemsContent`.
"""

from app.services.catalog import Scenario
from app.services.listen_prompts import (
    EVENT_SETTINGS,
    LANGUAGES,
    LEVEL_BRIEFS,
    Prompt,
    register_brief,
)
from app.services.planner import Level

SYSTEM_PROMPT = (
    "You choose vocabulary for adults preparing for a real event in a foreign language: "
    "short, useful phrases they will say or hear, each with a natural English "
    "translation. You reply only with the requested JSON."
)


def vocab_items_prompt(
    language: str, scenario: Scenario, level: Level, count: int, existing_phrases: list[str]
) -> Prompt:
    """The prompt for `count` Vocab Items in `language` for the Scenario, at the Level,
    none repeating `existing_phrases`.

    Raises KeyError for a language there's no prompt for (only Spanish in the MVP).
    """
    language_name = LANGUAGES[language]
    existing = "\n".join(f"- {phrase}" for phrase in existing_phrases) or "(none yet)"
    return Prompt(
        system=SYSTEM_PROMPT,
        user="\n\n".join(
            (
                f"Choose {count} {language_name} phrases for a learner preparing for "
                f"{EVENT_SETTINGS[scenario.event_type]}. The situation: "
                f'"{scenario.title}".',
                f"Level: {LEVEL_BRIEFS[level]} Pick phrases a learner at this Level needs "
                "next: harder than the basics below, but no harder than the Level allows.",
                f"Register: {register_brief(scenario)}",
                (
                    "Each item is one phrase or short sentence the learner would really use "
                    "or hear in this situation, in `phrase`, with its English meaning in "
                    "`translation`. Every phrase is different from the others and from "
                    "these phrases the learner already has, even ignoring case, accents "
                    f"and punctuation:\n{existing}"
                ),
                f"Return exactly {count} items, most useful first.",
            )
        ),
    )
