"""Regression tests for dashboard startup compatibility with older jarvis_common modules."""
import ast
from pathlib import Path


def _load_dashboard_history_formatter():
    source = Path("dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "jarvis_common"
        for alias in node.names
    }
    assert "format_conversation_history" not in imported_names

    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "format_conversation_history"
    )
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {}
    exec(compile(isolated, "dashboard.py", "exec"), namespace)
    return namespace["format_conversation_history"]


def test_dashboard_has_local_conversation_formatter():
    formatter = _load_dashboard_history_formatter()
    history = formatter(
        [("user", "old"), ("assistant", "old answer"),
         ("user", "latest question"), ("assistant", "latest answer")],
        max_chars=50,
        max_message_chars=40,
    )
    assert "latest question" in history
    assert "latest answer" in history
    assert "old" not in history


def test_dashboard_formatter_enforces_message_and_total_limits():
    formatter = _load_dashboard_history_formatter()
    history = formatter([("user", "x" * 200)], max_chars=50, max_message_chars=30)
    assert len(history) <= 50
    assert "rövidítve" in history


def test_dashboard_formatter_ignores_unknown_roles_and_invalid_limits():
    formatter = _load_dashboard_history_formatter()
    assert formatter([("system", "must be ignored")]) == ""
    assert formatter([("user", "hello")], max_chars=0) == ""
