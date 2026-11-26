"""The checks every Listen Dialogue passes, hand-written or generated."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.services.listen_content import ListenDialogueContent


def dialogue(**changes: Any) -> dict[str, Any]:
    """A valid Listen Dialogue, as plain data, with `changes` applied."""
    base: dict[str, Any] = {
        "speakers": ["Lucía", "Marcos"],
        "lines": [
            {"speaker": "Lucía", "text": "Buenos días. ¿Es usted Marcos?"},
            {"speaker": "Marcos", "text": "Sí, soy yo. Mucho gusto."},
            {"speaker": "Lucía", "text": "Encantada. Siéntese, por favor."},
            {"speaker": "Marcos", "text": "Gracias. He venido en metro."},
            {"speaker": "Lucía", "text": "¿Ha tardado mucho?"},
            {"speaker": "Marcos", "text": "No, solo veinte minutos."},
        ],
        "questions": [
            {
                "prompt": "Who asks Marcos to sit down?",
                "options": ["Lucía", "Marcos", "Nobody"],
                "correct_option": 1,
                "supporting_line": "Siéntese, por favor.",
            },
            {
                "prompt": "How did Marcos get there?",
                "options": ["By bus", "By metro", "On foot"],
                "correct_option": 2,
                "supporting_line": "He venido en metro.",
            },
            {
                "prompt": "How long did the trip take?",
                "options": ["Ten minutes", "An hour", "Twenty minutes"],
                "correct_option": 3,
                "supporting_line": "solo veinte minutos",
            },
        ],
    }
    return {**base, **changes}


def test_a_valid_dialogue_is_accepted() -> None:
    content = ListenDialogueContent.model_validate(dialogue())

    assert content.speakers == ["Lucía", "Marcos"]
    assert [q.correct_option for q in content.questions] == [1, 2, 3]


def lines(count: int) -> list[dict[str, str]]:
    return [
        {"speaker": ["Lucía", "Marcos"][n % 2], "text": f"Línea {n}. He venido en metro."}
        for n in range(count)
    ]


@pytest.mark.parametrize("count", [6, 12])
def test_six_to_twelve_lines_are_accepted(count: int) -> None:
    ListenDialogueContent.model_validate(dialogue(lines=lines(count), questions=same_questions()))


@pytest.mark.parametrize("count", [5, 13])
def test_fewer_than_six_or_more_than_twelve_lines_are_rejected(count: int) -> None:
    with pytest.raises(ValidationError):
        ListenDialogueContent.model_validate(
            dialogue(lines=lines(count), questions=same_questions())
        )


def same_questions() -> list[dict[str, Any]]:
    """Three questions all supported by "He venido en metro."."""
    return [
        {
            "prompt": f"Question {n}?",
            "options": ["A", "B", "C"],
            "correct_option": 1,
            "supporting_line": "He venido en metro.",
        }
        for n in range(3)
    ]


@pytest.mark.parametrize(
    "speakers", [["Lucía"], ["Lucía", "Marcos", "Ana"], ["Lucía", "Lucía"], ["Lucía", " "]]
)
def test_anything_but_two_distinct_named_speakers_is_rejected(speakers: list[str]) -> None:
    with pytest.raises(ValidationError):
        ListenDialogueContent.model_validate(dialogue(speakers=speakers))


def test_a_line_by_someone_who_isnt_one_of_the_speakers_is_rejected() -> None:
    changed = dialogue()
    changed["lines"][2]["speaker"] = "Ana"

    with pytest.raises(ValidationError, match="Ana"):
        ListenDialogueContent.model_validate(changed)


def test_a_speaker_who_never_speaks_is_rejected() -> None:
    changed = dialogue()
    for line in changed["lines"]:
        line["speaker"] = "Lucía"

    with pytest.raises(ValidationError, match="Marcos"):
        ListenDialogueContent.model_validate(changed)


@pytest.mark.parametrize("count", [2, 4])
def test_anything_but_three_questions_is_rejected(count: int) -> None:
    questions = (dialogue()["questions"] * 2)[:count]

    with pytest.raises(ValidationError):
        ListenDialogueContent.model_validate(dialogue(questions=questions))


@pytest.mark.parametrize(
    "options", [["Lucía", "Marcos"], ["Lucía", "Marcos", "Nobody", "Ana"], ["Lucía", "lucía", "X"]]
)
def test_anything_but_three_distinct_options_is_rejected(options: list[str]) -> None:
    changed = dialogue()
    changed["questions"][0]["options"] = options

    with pytest.raises(ValidationError):
        ListenDialogueContent.model_validate(changed)


@pytest.mark.parametrize("correct_option", [0, 4])
def test_a_correct_option_out_of_range_is_rejected(correct_option: int) -> None:
    changed = dialogue()
    changed["questions"][1]["correct_option"] = correct_option

    with pytest.raises(ValidationError):
        ListenDialogueContent.model_validate(changed)


def test_a_supporting_line_that_isnt_in_the_dialogue_is_rejected() -> None:
    changed = dialogue()
    changed["questions"][2]["supporting_line"] = "Ha tardado una hora."

    with pytest.raises(ValidationError, match="una hora"):
        ListenDialogueContent.model_validate(changed)


def test_a_supporting_line_matches_ignoring_extra_whitespace() -> None:
    changed = dialogue()
    changed["questions"][2]["supporting_line"] = "  solo   veinte minutos "

    ListenDialogueContent.model_validate(changed)
