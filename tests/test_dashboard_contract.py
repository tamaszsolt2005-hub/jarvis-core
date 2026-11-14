"""Static contract tests for the chat-first, read-only dashboard."""
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard.py"


def _function_node(source: str, name: str):
    tree = ast.parse(source)
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def test_dashboard_compiles_and_has_read_only_retrieval():
    source = DASHBOARD.read_text(encoding="utf-8")
    tree = ast.parse(source)
    retrieval = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "retrieve_context"
    )
    called_methods = {
        node.func.attr
        for node in ast.walk(retrieval)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "select" in called_methods
    assert not ({"insert", "update", "upsert", "delete"} & called_methods)


def test_dashboard_uses_chat_input_as_primary_interaction():
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "st.chat_input(" in source
    assert "st.chat_message(" in source


def test_dashboard_does_not_enable_automatic_email_sending():
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "AUTO_SEND_ENABLED" not in source
    assert "nem küldhetsz e-mailt" in source
