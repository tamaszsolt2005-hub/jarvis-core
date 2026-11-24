"""Behavioral checks for dashboard authentication and repository authorization boundaries."""
import ast
import contextlib
import hmac
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SOURCE = (ROOT / "dashboard.py").read_text(encoding="utf-8")
DASHBOARD_TREE = ast.parse(DASHBOARD_SOURCE)


def _load_authenticated(*, session_state, now, expected_password=None, submitted=False, password=""):
    function = next(
        node for node in DASHBOARD_TREE.body
        if isinstance(node, ast.FunctionDef) and node.name == "authenticated"
    )

    class FakeStreamlit:
        def __init__(self):
            self.session_state = session_state
            self.errors = []
            self.rerun_called = False

        def error(self, message):
            self.errors.append(message)

        def markdown(self, *_args, **_kwargs):
            pass

        def title(self, *_args, **_kwargs):
            pass

        def caption(self, *_args, **_kwargs):
            pass

        def form(self, *_args, **_kwargs):
            return contextlib.nullcontext()

        def text_input(self, *_args, **_kwargs):
            return password

        def form_submit_button(self, *_args, **_kwargs):
            return submitted

        def rerun(self):
            self.rerun_called = True

    fake_st = FakeStreamlit()
    namespace = {
        "st": fake_st,
        "time": SimpleNamespace(time=lambda: now),
        "hmac": hmac,
        "get_secret": lambda _name: expected_password,
        "AUTH_SESSION_TTL_SECONDS": 8 * 60 * 60,
        "_auth_login_enabled": lambda: False,
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(ROOT / "dashboard.py"), "exec"), namespace)
    return namespace["authenticated"](), fake_st


def test_valid_unexpired_dashboard_session_is_accepted():
    accepted, _ = _load_authenticated(
        session_state={"authenticated": True, "_jarvis_authenticated_at": 9_950},
        now=10_000,
        expected_password="configured-secret",
    )
    assert accepted is True


def test_expired_session_is_rejected_and_sensitive_session_state_is_cleared():
    state = {
        "authenticated": True,
        "_jarvis_authenticated_at": 1,
        "_jarvis_db": object(),
        "_jarvis_pending_action": {"task_action": {"type": "create"}},
    }
    accepted, _ = _load_authenticated(
        session_state=state, now=40_000, expected_password=None
    )
    assert accepted is False
    assert "authenticated" not in state
    assert "_jarvis_authenticated_at" not in state
    assert "_jarvis_db" not in state
    assert "_jarvis_pending_action" not in state


def test_session_without_timestamp_is_not_trusted():
    state = {"authenticated": True, "_jarvis_db": object()}
    accepted, _ = _load_authenticated(
        session_state=state, now=10_000, expected_password=None
    )
    assert accepted is False
    assert "authenticated" not in state
    assert "_jarvis_db" not in state


def test_future_dated_session_is_rejected():
    state = {"authenticated": True, "_jarvis_authenticated_at": 10_001}
    accepted, _ = _load_authenticated(
        session_state=state, now=10_000, expected_password=None
    )
    assert accepted is False
    assert "authenticated" not in state


def test_wrong_dashboard_password_does_not_create_authenticated_session():
    state = {}
    accepted, ui = _load_authenticated(
        session_state=state,
        now=10_000,
        expected_password="correct-secret",
        submitted=True,
        password="wrong-secret",
    )
    assert accepted is False
    assert "authenticated" not in state
    assert ui.errors == ["Hibás jelszó."]


def test_correct_dashboard_password_sets_timestamped_session():
    state = {}
    accepted, ui = _load_authenticated(
        session_state=state,
        now=10_000,
        expected_password="correct-secret",
        submitted=True,
        password="correct-secret",
    )
    assert accepted is False  # Streamlit reruns after successful login.
    assert state["authenticated"] is True
    assert state["_jarvis_authenticated_at"] == 10_000
    assert ui.rerun_called is True


def test_dashboard_stops_before_rendering_private_workspace_without_authentication():
    gate = next(
        node for node in DASHBOARD_TREE.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Call)
        and isinstance(node.test.operand.func, ast.Name)
        and node.test.operand.func.id == "authenticated"
    )
    assert any(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "stop"
        for node in gate.body
    )


def test_every_repository_application_table_has_rls_enabled_in_schema():
    schema = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8").lower()
    tables = (
        "leads", "logs", "settings", "tasks", "email_drafts",
        "jarvis_memory", "jarvis_proactive_state",
    )
    for table in tables:
        assert f"alter table public.{table} enable row level security;" in schema


def test_dashboard_passes_approval_only_from_the_explicit_confirmation_branch():
    assert "execute_task_action(" in DASHBOARD_SOURCE
    assert "approved=True" in DASHBOARD_SOURCE

    task_source = (ROOT / "task_actions.py").read_text(encoding="utf-8")
    assert "approved: bool = False" in task_source
    assert "if approved is not True:" in task_source
    assert "raise PermissionError" in task_source




def test_pending_approval_is_consumed_before_task_execution_to_prevent_replay():
    approval_start = DASHBOARD_SOURCE.index('elif q in {"jóváhagyom"')
    consume_index = DASHBOARD_SOURCE.index(
        'st.session_state.pop("_jarvis_pending_action", None)', approval_start
    )
    execute_index = DASHBOARD_SOURCE.index(
        "execute_task_action(", approval_start
    )
    assert consume_index < execute_index


def test_new_chat_request_invalidates_previous_pending_approval():
    invalidation_comment = DASHBOARD_SOURCE.index(
        "# A pending approval is valid for exactly the next user message."
    )
    invalidate_index = DASHBOARD_SOURCE.index(
        'st.session_state.pop("_jarvis_pending_action", None)', invalidation_comment
    )
    parse_index = DASHBOARD_SOURCE.index(
        "requested_task_action = parse_task_command(prompt)", invalidation_comment
    )
    assert invalidation_comment < invalidate_index < parse_index



def test_audit_csv_export_uses_verified_admin_jwt_and_expires():
    audit_page = next(
        node for node in DASHBOARD_TREE.body
        if isinstance(node, ast.FunctionDef) and node.name == "render_audit_admin_page"
    )
    source = ast.unparse(audit_page)
    assert "verified_admin_client(session)" in source
    assert "audit_client" in source
    assert "get_legacy_dashboard_supabase" not in source
    assert "_audit_export_is_valid" in source
    assert "time.time()" in source
