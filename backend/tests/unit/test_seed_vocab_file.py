"""The committed seed vocabulary file covers the whole Scenario Catalog."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.catalog import SCENARIO_CATALOG
from app.services.seed_vocab import read_seed_vocab

MIN_ITEMS_PER_SCENARIO = 12


def test_the_spanish_seed_file_gives_every_catalog_scenario_at_least_12_items() -> None:
    seed = read_seed_vocab()

    assert seed.language == "es"
    for scenario in SCENARIO_CATALOG:
        items = seed.scenarios.get(scenario.slug, [])
        assert len(items) >= MIN_ITEMS_PER_SCENARIO, scenario.slug


def test_the_spanish_seed_file_has_no_phrase_twice_within_a_scenario() -> None:
    for slug, items in read_seed_vocab().scenarios.items():
        phrases = [item.phrase.casefold() for item in items]
        assert len(phrases) == len(set(phrases)), slug


def write_seed(tmp_path: Path, scenarios: dict[str, list[dict[str, str]]]) -> Path:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps({"language": "es", "scenarios": scenarios}), encoding="utf-8")
    return path


HELLO = {"item_key": "hello", "phrase": "Hola.", "translation": "Hello."}


def test_a_seed_file_with_a_slug_outside_the_catalog_is_rejected(tmp_path: Path) -> None:
    path = write_seed(tmp_path, {"interview.made_up": [HELLO]})

    with pytest.raises(ValidationError, match=r"interview\.made_up"):
        read_seed_vocab(path)


def test_a_seed_file_with_a_repeated_key_in_a_scenario_is_rejected(tmp_path: Path) -> None:
    path = write_seed(tmp_path, {"relocation.airport_arrival": [HELLO, HELLO]})

    with pytest.raises(ValidationError, match="hello"):
        read_seed_vocab(path)


def test_a_seed_file_with_a_key_in_the_generated_items_namespace_is_rejected(
    tmp_path: Path,
) -> None:
    # Generated items' keys start with gen_, so they can never collide with a seed key.
    path = write_seed(
        tmp_path, {"relocation.airport_arrival": [{**HELLO, "item_key": "gen_hello"}]}
    )

    with pytest.raises(ValidationError, match="gen_hello"):
        read_seed_vocab(path)


@pytest.mark.parametrize("key", ["Hello", "hello-there", "1st", ""])
def test_a_seed_file_with_a_key_that_isnt_snake_case_is_rejected(tmp_path: Path, key: str) -> None:
    path = write_seed(tmp_path, {"relocation.airport_arrival": [{**HELLO, "item_key": key}]})

    with pytest.raises(ValidationError):
        read_seed_vocab(path)
