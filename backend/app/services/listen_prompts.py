"""The prompts that ask an LLM for a Listen Dialogue.

Pure: plain strings built from the Scenario Catalog and the Level. The prompt gets the
Scenario's title and Event Type, a hand-written brief for the Level, and the register
(Spanish as spoken in Spain, `usted` where the Scenario is formal). The Event's
free-text goals are never used, so the content suits everyone who shares its
(language, Scenario, Level) key (ADR 0008). The response's shape and checks live on
`ListenDialogueContent`, which instructor sends as the schema.
"""

from dataclasses import dataclass

from app.services.catalog import EventType, Scenario
from app.services.listen_content import MAX_LINES, MIN_LINES, OPTION_COUNT, QUESTION_COUNT
from app.services.planner import Level

# What each CEFR Level can follow: the tenses, how long a line gets, and how common the
# words are. Kept short: it steers the dialogue, it isn't a syllabus.
LEVEL_BRIEFS: dict[Level, str] = {
    Level.A1: (
        "A1 (beginner). Present tense, plus 'ir a' + infinitive for plans. Lines of 4 to "
        "10 words. Only the most common everyday words; no idioms. Questions and options "
        "use the same simple words as the dialogue."
    ),
    Level.A2: (
        "A2 (elementary). Present, pretérito perfecto and pretérito indefinido for "
        "simple past events, 'ir a' for plans. Lines of up to 15 words. Common words, a "
        "few fixed polite phrases; no idioms."
    ),
    Level.B1: (
        "B1 (intermediate). Past tenses including the imperfecto, the future, and simple "
        "uses of the subjunctive after 'quiero que' or 'espero que'. Lines of up to 20 "
        "words, some joined with 'porque', 'aunque' or 'cuando'. Everyday and work "
        "vocabulary; one or two common expressions."
    ),
    Level.B2: (
        "B2 (upper intermediate). Any indicative tense, the present and imperfect "
        "subjunctive, and conditionals. Lines of up to 25 words with natural connectors. "
        "Precise vocabulary for the situation and a few idiomatic expressions. Questions "
        "may need the listener to infer what a speaker means."
    ),
    Level.C1: (
        "C1 (advanced). The full range of tenses and moods, including hypotheticals. "
        "Natural, fluent lines of any length up to 30 words, with nuance, hedging and "
        "idiomatic expressions a native speaker would use. Questions test implied "
        "meaning and attitude, not just stated facts."
    ),
}

# Scenarios where Spaniards would normally move from `usted` to `tú`: small talk after
# a speech starts formally and often switches once someone offers. Every other Scenario
# is formal: an interview, dealing with officials, landlords, banks and doctors, or
# speaking to an audience (`ustedes`).
_SWITCHES_TO_TU = frozenset({"speech.small_talk_afterwards"})

EVENT_SETTINGS: dict[EventType, str] = {
    EventType.INTERVIEW: "a job interview in Spain",
    EventType.RELOCATION: "moving to and settling in Spain",
    EventType.SPEECH: "giving a speech in Spain",
}

LANGUAGES = {"es": "Spanish"}

SYSTEM_PROMPT = (
    "You write short listening-comprehension material for adults preparing for a real "
    "event in a foreign language. You write natural, realistic dialogues and fair "
    "multiple-choice questions whose answers are stated or clearly implied in the "
    "dialogue. You reply only with the requested JSON."
)


@dataclass(frozen=True)
class Prompt:
    """The system prompt and the user message for one call."""

    system: str
    user: str


def listen_dialogue_prompt(language: str, scenario: Scenario, level: Level) -> Prompt:
    """The prompt for one Listen Dialogue in `language`, set in the Scenario, at the Level.

    Raises KeyError for a language there's no prompt for (only Spanish in the MVP).
    """
    language_name = LANGUAGES[language]
    return Prompt(
        system=SYSTEM_PROMPT,
        user="\n\n".join(
            (
                f"Write a short conversation in {language_name} for a learner preparing "
                f"for {EVENT_SETTINGS[scenario.event_type]}. The situation: "
                f'"{scenario.title}".',
                f"Level: {LEVEL_BRIEFS[level]}",
                f"Register: {register_brief(scenario)}",
                (
                    f"The conversation has {MIN_LINES} to {MAX_LINES} lines between exactly "
                    "two speakers, each with a common Spanish first name (or a first name "
                    "and surname where that's natural). List both names in `speakers`, and "
                    "give each line's speaker exactly as listed. Both speakers talk. Make "
                    "it a realistic exchange the learner might hear, with concrete details "
                    "(names, times, numbers, places) worth listening for."
                ),
                (
                    f"Then write {QUESTION_COUNT} multiple-choice questions in "
                    f"{language_name} about what was said, at the same Level. Each has "
                    f"{OPTION_COUNT} different options, exactly one of them right; the "
                    "wrong ones are plausible. `correct_option` is the number of the right "
                    f"option, from 1 to {OPTION_COUNT}; vary it across the questions. "
                    "`supporting_line` copies, word for word, the part of one line that "
                    "answers the question. Each question is about a different line."
                ),
            )
        ),
    )


def register_brief(scenario: Scenario) -> str:
    """How the Spanish should sound in this Scenario: Spain's, formal or not."""
    base = (
        "Spanish as spoken in Spain (Castilian): Spain's vocabulary and expressions, "
        "'vosotros' rather than 'ustedes' for an informal 'you all', and no Latin "
        "American usage."
    )
    if scenario.slug in _SWITCHES_TO_TU:
        return (
            f"{base} The speakers start with 'usted' and may switch to 'tú' if one of "
            "them suggests it."
        )
    return (
        f"{base} This is a formal situation: the speakers address each other with "
        "'usted' (and an audience with 'ustedes')."
    )
