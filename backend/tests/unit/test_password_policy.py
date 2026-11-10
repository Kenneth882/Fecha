import pytest

from app.services.password_policy import PasswordRule, broken_password_rule

COMMON = frozenset({"password1!", "qwerty123$"})


def test_a_long_password_with_a_digit_and_a_special_character_breaks_no_rule() -> None:
    assert broken_password_rule("violet-kettle-47", COMMON) is None


@pytest.mark.parametrize(
    ("password", "rule"),
    [
        ("a1!bcde", PasswordRule.TOO_SHORT),
        ("violet-kettle", PasswordRule.NO_DIGIT),
        ("violetkettle47", PasswordRule.NO_SPECIAL_CHARACTER),
        ("Password1!", PasswordRule.COMMON),
    ],
)
def test_each_rule_is_reported_when_it_alone_is_broken(password: str, rule: PasswordRule) -> None:
    assert broken_password_rule(password, COMMON) is rule


def test_exactly_eight_characters_is_long_enough() -> None:
    assert broken_password_rule("abcde1!x", COMMON) is None


def test_length_counts_characters_not_bytes() -> None:
    # Seven characters, though more than eight bytes in UTF-8.
    assert broken_password_rule("ñañañ1!", COMMON) is PasswordRule.TOO_SHORT


def test_the_common_list_is_matched_ignoring_letter_case() -> None:
    assert broken_password_rule("QWERTY123$", COMMON) is PasswordRule.COMMON


def test_only_ascii_digits_count_as_digits() -> None:
    # "٤" is ARABIC-INDIC DIGIT FOUR: a Unicode digit, but not 0-9.
    assert broken_password_rule("violet-kettle-٤", COMMON) is PasswordRule.NO_DIGIT


@pytest.mark.parametrize("special", ["!", "-", "_", "€", "§", "😀"])
def test_any_non_letter_non_digit_non_space_character_is_special(special: str) -> None:
    assert broken_password_rule(f"violetkettle47{special}", COMMON) is None


def test_whitespace_is_not_a_special_character() -> None:
    assert broken_password_rule("violet kettle 47", COMMON) is PasswordRule.NO_SPECIAL_CHARACTER


def test_accented_letters_are_letters_not_special_characters() -> None:
    assert broken_password_rule("contraseñaüé47", COMMON) is PasswordRule.NO_SPECIAL_CHARACTER


def test_the_first_broken_rule_is_reported() -> None:
    # Short, with no digit and no special character: length comes first.
    assert broken_password_rule("abc", COMMON) is PasswordRule.TOO_SHORT
