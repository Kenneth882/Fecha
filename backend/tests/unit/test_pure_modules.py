"""The pure modules stay pure: no FastAPI, SQLAlchemy, Redis or network imports.

CLAUDE.md keeps the planner (and the catalog it reads) free of I/O so it stays trivially
testable. This checks the source rather than trusting review to notice.
"""

import ast
import sys
from pathlib import Path

import pytest

SERVICES = Path(__file__).parents[2] / "app" / "services"

ALLOWED = {
    "catalog.py": {"pydantic"},
    "planner.py": {"pydantic", "app.services.catalog"},
    "task_status.py": set(),
}


def imported_modules(source: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"relative import in {source.name}"
            assert node.module is not None
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("filename", sorted(ALLOWED))
def test_a_pure_module_imports_only_the_standard_library_and_its_allowed_modules(
    filename: str,
) -> None:
    imported = imported_modules(SERVICES / filename)
    outside_stdlib = {m for m in imported if m.split(".")[0] not in sys.stdlib_module_names}

    assert outside_stdlib <= ALLOWED[filename]
