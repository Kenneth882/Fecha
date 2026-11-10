"""Regenerate app/data/common-password-patterns.txt.

The SecLists top-100k list is mostly passwords the other rules already reject
(`123456`, `qwerty`). This adds the predictable ones that pass them: a common word
plus a digit-and-symbol suffix (`Password1!`, `Summer2026!`), and leetspeak.

Run from backend/: `uv run python -m scripts.build_common_password_patterns`
"""

from pathlib import Path

from app.services.password_policy import broken_password_rule

OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "common-password-patterns.txt"

BASE_WORDS = [
    "password",
    "passw0rd",
    "p@ssword",
    "p@ssw0rd",
    "p@55w0rd",
    "pa55word",
    "pa$$word",
    "welcome",
    "welc0me",
    "qwerty",
    "qwertyuiop",
    "asdfgh",
    "zxcvbn",
    "letmein",
    "admin",
    "administrator",
    "root",
    "user",
    "login",
    "iloveyou",
    "monkey",
    "dragon",
    "football",
    "baseball",
    "soccer",
    "basketball",
    "sunshine",
    "princess",
    "master",
    "shadow",
    "superman",
    "batman",
    "starwars",
    "pokemon",
    "trustno1",
    "hello",
    "hello123",
    "secret",
    "changeme",
    "default",
    "abc",
    "abcdef",
    "abcd",
    "test",
    "test123",
    "summer",
    "winter",
    "spring",
    "autumn",
    "fall",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "monday",
    "friday",
    "welcome1",
    "contrasena",
    "contraseña",
    "hola",
    "espana",
    "españa",
    "madrid",
    "barcelona",
    "mexico",
    "spain",
    "cramplan",
]

SUFFIXES = [
    *[
        "1!",
        "12!",
        "123!",
        "1234!",
        "12345!",
        "!1",
        "!123",
        "1@",
        "@1",
        "123@",
        "@123",
        "1#",
        "#1",
        "123#",
        "1$",
        "123$",
    ],
    *[
        "1.",
        "123.",
        "1*",
        "123*",
        "_1",
        "_123",
        "-1",
        "-123",
        "1?",
        "01!",
        "11!",
        "69!",
        "99!",
        "007!",
    ],
    *(f"{year}{s}" for year in range(2015, 2031) for s in "!@#$.*"),
    *(f"{s}{year}" for year in range(2015, 2031) for s in "!@#_-"),
]

LEETSPEAK = [
    "p@ssw0rd",
    "p@55w0rd",
    "p@$$w0rd",
    "pa$$w0rd",
    "passw0rd!",
    "p@ssw0rd!",
    "1qaz!qaz",
    "1qaz@wsx",
    "!qaz2wsx",
    "1q2w3e4r!",
    "1q2w3e4r5t!",
    "!q2w3e4r",
    "q1w2e3r4!",
    "qwer1234!",
    "abc123!@#",
    "123qwe!@#",
    "!@#123qwe",
    "1234qwer!",
    "zaq1@wsx",
    "zaq12wsx!",
]


def main() -> None:
    candidates = {word + suffix for word in BASE_WORDS for suffix in SUFFIXES} | set(LEETSPEAK)
    # Keep only what the other rules let through: anything else is caught already.
    entries = sorted(
        {c.lower() for c in candidates if broken_password_rule(c, frozenset()) is None}
    )
    OUT.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} passwords to {OUT}")


if __name__ == "__main__":
    main()
