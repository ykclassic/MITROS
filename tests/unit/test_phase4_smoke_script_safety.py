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


def test_phase4_smoke_has_hard_deployment_sha_gate_and_count_diagnostics() -> None:
    source = Path("scripts/run_phase4_smoke.py").read_text(encoding="utf-8")
    assert 'if deployed_sha != expected_sha:' in source
    assert 'requested_sha={expected_sha} deployed_sha={deployed_sha}' in source
    assert 'if any(count != 1 for count in counts.values()):' in source
    assert 'f"{name}={count}" for name, count in counts.items()' in source



def test_phase4_smoke_health_check_retries_transient_transport_failures() -> None:
    source = Path("scripts/run_phase4_smoke.py").read_text(encoding="utf-8")
    assert "def _health_request(" in source
    assert 'attempts: int = 3' in source
    assert 'time.sleep(retry_delay_seconds)' in source
    assert 'Production health check failed after {attempt} attempt(s): {message}' in source
    assert 'HTTP request returned invalid JSON' in source
