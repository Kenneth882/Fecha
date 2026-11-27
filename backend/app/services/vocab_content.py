"""What a generated batch of Vocab Items holds, the checks every batch passes, and how
near-duplicate phrases are found.

Pure: Pydantic and the standard library only. The batch size is given at validation
time, as `context={"count": n}`, which instructor passes through on every attempt, so a
response of the wrong size is sent back for a retry like any other failed check.
"""

import unicodedata
from collections.abc import Iterable
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationInfo, model_validator

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# How many generated Vocab Items each (language, Scenario, Level) key gets.
VOCAB_ITEM_COUNT = 10
# Generated Vocab Items start after this position, so seed items (numbered from 1 by
# the seed loader) can grow to this many per Scenario and still come first.
GENERATED_POSITIONS_AFTER = 1000


def phrase_key(phrase: str) -> str:
    """`phrase` with case, punctuation, accents and spacing taken out, so two phrases
    that differ only in those have the same key.

    Accents go with their letter's other marks, so "año" and "ano" share a key: a rare
    clash that only costs one generated item.
    """
    decomposed = unicodedata.normalize("NFKD", phrase.casefold())
    kept = (
        " " if unicodedata.category(char).startswith(("P", "Z")) else char
        for char in decomposed
        if not unicodedata.combining(char)
    )
    return " ".join("".join(kept).split())


class VocabItemContent(BaseModel):
    """One phrase in the target language, with its English translation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phrase: NonBlankText
    translation: NonBlankText


class VocabItemsContent(BaseModel):
    """A batch of Vocab Items for one Scenario, no two the same phrase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[VocabItemContent]

    @model_validator(mode="after")
    def _right_size_without_repeats(self, info: ValidationInfo) -> Self:
        count = (info.context or {}).get("count")
        if count is None:
            raise ValueError("validate with context={'count': n}, the batch size asked for")
        if len(self.items) != count:
            raise ValueError(f"there are {len(self.items)} items, not the {count} asked for")
        seen: set[str] = set()
        for item in self.items:
            key = phrase_key(item.phrase)
            if key in seen:
                raise ValueError(f"{item.phrase!r} is in the list twice")
            seen.add(key)
        return self


def new_items(
    content: VocabItemsContent, existing_phrases: Iterable[str]
) -> list[VocabItemContent]:
    """The batch's items whose phrase doesn't match any of `existing_phrases`, in order."""
    existing = {phrase_key(phrase) for phrase in existing_phrases}
    return [item for item in content.items if phrase_key(item.phrase) not in existing]
