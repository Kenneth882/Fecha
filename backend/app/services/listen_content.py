"""What a Listen Dialogue holds, and the checks every one passes.

Pure: Pydantic only. The hand-written fallback file and, later, LLM generation both
produce `ListenDialogueContent`, so a dialogue that reaches a User has always passed
the same checks. Option and question numbers count from 1.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

MIN_LINES = 6
MAX_LINES = 12
QUESTION_COUNT = 3
OPTION_COUNT = 3


def _squeeze(text: str) -> str:
    """`text` with runs of whitespace made one space, and trimmed."""
    return " ".join(text.split())


class DialogueLine(BaseModel):
    """One line of a Listen Dialogue: who says it, and what they say."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    speaker: NonBlankText
    text: NonBlankText


class ComprehensionQuestionContent(BaseModel):
    """A multiple-choice question about a Listen Dialogue.

    `correct_option` is the number of the right option, from 1. `supporting_line` quotes
    the part of the dialogue that answers it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: NonBlankText
    options: Annotated[list[NonBlankText], Field(min_length=OPTION_COUNT, max_length=OPTION_COUNT)]
    correct_option: Annotated[int, Field(ge=1, le=OPTION_COUNT)]
    supporting_line: NonBlankText

    @model_validator(mode="after")
    def _options_are_distinct(self) -> Self:
        if len({option.casefold() for option in self.options}) != len(self.options):
            raise ValueError(f"{self.prompt!r} has the same option twice")
        return self


class ListenDialogueContent(BaseModel):
    """A short conversation between two named speakers, with three Comprehension
    Questions, each answered by a line of it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    speakers: Annotated[list[NonBlankText], Field(min_length=2, max_length=2)]
    lines: Annotated[list[DialogueLine], Field(min_length=MIN_LINES, max_length=MAX_LINES)]
    questions: Annotated[
        list[ComprehensionQuestionContent],
        Field(min_length=QUESTION_COUNT, max_length=QUESTION_COUNT),
    ]

    @model_validator(mode="after")
    def _speakers_and_supporting_lines_match_the_lines(self) -> Self:
        if self.speakers[0] == self.speakers[1]:
            raise ValueError("the two speakers have the same name")
        speaking = {line.speaker for line in self.lines}
        if strangers := speaking - set(self.speakers):
            raise ValueError(f"lines are spoken by {sorted(strangers)}, who aren't speakers")
        if silent := set(self.speakers) - speaking:
            raise ValueError(f"{sorted(silent)} never speaks")
        texts = [_squeeze(line.text) for line in self.lines]
        for question in self.questions:
            quote = _squeeze(question.supporting_line)
            if not any(quote in text for text in texts):
                raise ValueError(
                    f"{question.prompt!r}: its supporting line {quote!r} isn't in the dialogue"
                )
        return self
