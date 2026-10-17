from __future__ import annotations

import ast
from pathlib import Path


def test_phase4_smoke_executes_only_fixed_select_statements() -> None:
    source_path = Path("scripts/run_phase4_smoke.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    statements: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "execute":
            continue
        assert node.args, "SQL execute call must have a fixed statement argument"
        statement = node.args[0]
        assert isinstance(statement, ast.Constant) and isinstance(statement.value, str), (
            "SQL must be a literal constant; dynamic SQL is prohibited"
        )
        statements.append(statement.value.strip())

    assert len(statements) == 4
    assert all(statement.upper().startswith("SELECT ") for statement in statements)
    assert all("%s" in statement or "current_database" in statement for statement in statements)


def test_phase4_smoke_database_session_is_server_enforced_read_only() -> None:
    source = Path("scripts/run_phase4_smoke.py").read_text(encoding="utf-8")
    assert 'options="-c default_transaction_read_only=on"' in source
