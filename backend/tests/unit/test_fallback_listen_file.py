"""The committed fallback Listen Dialogues cover the whole Scenario Catalog."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.catalog import SCENARIO_CATALOG
from app.services.fallback_listen import read_fallback_dialogues
from tests.unit.test_listen_dialogue_content import dialogue


def test_the_spanish_file_has_exactly_one_dialogue_for_every_catalog_scenario() -> None:
    fallbacks = read_fallback_dialogues()

    assert fallbacks.language == "es"
    assert sorted(fallbacks.dialogues) == sorted(s.slug for s in SCENARIO_CATALOG)


def test_no_two_spanish_fallbacks_share_a_line() -> None:
    # A copy-pasted dialogue would pass every check, so look for one.
    seen: dict[str, str] = {}
    for slug, content in read_fallback_dialogues().dialogues.items():
        for line in content.lines:
            assert line.text not in seen, f"{slug} repeats a line of {seen.get(line.text)}"
            seen[line.text] = slug


def write_file(tmp_path: Path, dialogues: dict[str, Any]) -> Path:
    path = tmp_path / "listen.json"
    path.write_text(json.dumps({"language": "es", "dialogues": dialogues}), encoding="utf-8")
    return path


def test_a_file_with_a_slug_outside_the_catalog_is_rejected(tmp_path: Path) -> None:
    path = write_file(tmp_path, {"interview.made_up": dialogue()})

    with pytest.raises(ValidationError, match=r"interview\.made_up"):
        read_fallback_dialogues(path)


def test_a_file_with_a_dialogue_that_fails_the_checks_is_rejected(tmp_path: Path) -> None:
    path = write_file(tmp_path, {"relocation.airport_arrival": dialogue(speakers=["Lucía"])})

    with pytest.raises(ValidationError):
        read_fallback_dialogues(path)
