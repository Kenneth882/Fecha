"""The checks every generated batch of Vocab Items passes, and how near-duplicate phrases
are found."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.services.vocab_content import VocabItemsContent, new_items, phrase_key


def items(count: int) -> list[dict[str, str]]:
    return [
        {"phrase": f"Frase número {n}", "translation": f"Phrase number {n}"} for n in range(count)
    ]


def validate(data: dict[str, Any], count: int) -> VocabItemsContent:
    return VocabItemsContent.model_validate(data, context={"count": count})


def test_a_batch_of_the_requested_size_is_accepted() -> None:
    content = validate({"items": items(3)}, count=3)

    assert [item.phrase for item in content.items] == [
        "Frase número 0",
        "Frase número 1",
        "Frase número 2",
    ]


@pytest.mark.parametrize("size", [2, 4])
def test_a_batch_of_another_size_is_rejected(size: int) -> None:
    with pytest.raises(ValidationError, match="3"):
        validate({"items": items(size)}, count=3)


@pytest.mark.parametrize("field", ["phrase", "translation"])
def test_every_item_needs_a_phrase_and_a_translation(field: str) -> None:
    batch = items(2)
    batch[1][field] = "   "

    with pytest.raises(ValidationError):
        validate({"items": batch}, count=2)


def test_a_batch_repeating_a_phrase_is_rejected() -> None:
    batch = [
        {"phrase": "¿Dónde está la estación?", "translation": "Where is the station?"},
        {"phrase": "donde esta  la estacion", "translation": "Where's the station?"},
    ]

    with pytest.raises(ValidationError, match="twice"):
        validate({"items": batch}, count=2)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Buenos días", "buenos días"),
        ("¿Qué tal?", "Qué tal"),
        ("¡Encantado!", "encantado"),
        ("Está bien", "Esta bien"),
        ("  Muchas   gracias ", "Muchas gracias"),
        ("el año", "el ano"),
    ],
)
def test_phrases_differing_only_in_case_punctuation_accents_or_spacing_match(
    a: str, b: str
) -> None:
    assert phrase_key(a) == phrase_key(b)


def test_phrases_with_different_words_do_not_match() -> None:
    assert phrase_key("Buenos días") != phrase_key("Buenas noches")


def test_new_items_drops_phrases_matching_an_existing_one() -> None:
    content = validate(
        {
            "items": [
                {"phrase": "¡Mucho gusto!", "translation": "Nice to meet you!"},
                {"phrase": "Tengo experiencia", "translation": "I have experience"},
            ]
        },
        count=2,
    )

    kept = new_items(content, existing_phrases=["mucho gusto", "Soy ingeniera"])

    assert [item.phrase for item in kept] == ["Tengo experiencia"]
