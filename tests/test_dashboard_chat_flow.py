"""End-to-end contract tests for the Streamlit dashboard chat workflow.

These tests inspect the real dashboard control-flow source without starting Streamlit
or contacting external services. Side effects are verified by ordering and fail-closed
contracts; they are not a substitute for browser-driven AppTest/live integration tests.
"""
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "dashboard.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _call_positions(source, fragments):
    positions = []
    cursor = 0
    for fragment in fragments:
        position = source.find(fragment, cursor)
        assert position >= 0, fragment
        positions.append(position)
        cursor = position + len(fragment)


def _top_level_prompt_branch():
    return next(
        node for node in TREE.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "prompt"
    )


def _approval_branch():
    start = SOURCE.index('elif q in {"jóváhagyom"')
    end = SOURCE.index(
        "# A pending approval is valid for exactly the next user message.", start
    )
    return SOURCE[start:end]


def _chat_email_draft_branch():
    start = SOURCE.index("requested_chat_email = is_chat_email_request(prompt)")
    end = SOURCE.index("elif requested_task_action and requested_task_action.get", start)
    return SOURCE[start:end]


def test_private_ui_gate_precedes_sidebar_and_chat_rendering():
    _call_positions(SOURCE, [
        "if not authenticated():",
        "    st.stop()",
        "with st.sidebar:",
        'prompt = st.chat_input(',
    ])


def test_chat_history_is_rendered_before_input_and_new_user_turn_is_saved_first():
    _call_positions(SOURCE, [
        "for role, message in st.session_state.chat:",
        'prompt = st.chat_input(',
        'st.session_state.chat.append(("user", prompt))',
        'with st.chat_message("user"):',
        'request_id = uuid4().hex',
    ])


def test_chat_request_reuses_session_database_and_records_request_without_prompt_text():
    branch = _top_level_prompt_branch()
    branch_source = ast.get_source_segment(SOURCE, branch)
    _call_positions(branch_source, [
        'db = st.session_state.get("_jarvis_db")',
        "db = _get_dashboard_supabase()",
        'log_event(db, "chat", f"chat_request|request_id={request_id}")',
        "retrieve_context(db, prompt)",
    ])
    assert 'log_event(db, "chat", f"chat_request|request_id={request_id}")' in branch_source
    assert "log_event(db, \"chat\", prompt)" not in branch_source


def test_memory_mutations_are_routed_through_explicit_memory_commands():
    branch = _top_level_prompt_branch()
    source = ast.get_source_segment(SOURCE, branch)
    _call_positions(source, [
        "memory_action, memory_payload = memory_command(prompt)",
        'if memory_action == "save" or memory_action.startswith("save:"):',
        "save_memory(",
        "db, memory_payload",
        'elif memory_action == "forget":',
        "forget_memories(",
        "db, memory_payload",
    ])
    assert "get_memories(" in source
    assert "db, prompt, limit=100" in source


def test_chat_email_requires_single_explicit_recipient_and_prepares_preview_only():
    draft = _chat_email_draft_branch()
    _call_positions(draft, [
        "requested_chat_email = is_chat_email_request(prompt)",
        "recipient = extract_explicit_recipient(prompt)",
        "if not recipient:",
        "build_chat_email_draft(prompt, generate_text)",
        '_stage_pending_action({',
        "Jóváhagyásra váró e-mail-tervezet:",
    ])
    assert "send_email(" not in draft
    assert "Címzett: {recipient}" in draft
    assert "A levél nem ment ki." in draft


def test_chat_email_sending_requires_explicit_approval_and_both_server_switches():
    approval = _approval_branch()
    _call_positions(approval, [
        'elif q in {"jóváhagyom"',
        '_consume_pending_action(db)',
        'chat_email = pending_action.get("chat_email")',
        "if chat_email:",
        "if not EMAIL_DELIVERY_ENABLED or not env_bool(\"CHAT_EMAIL_ENABLED\", False):",
        'if not audit_event(db, status="pending", **audit_fields):',
        "send_email(",
        'audit_event(\n                            db, status="success"',
    ])
    assert "send_email(" not in SOURCE[SOURCE.index("if prompt:"):SOURCE.index("elif q in {") ]


def test_chat_email_pending_audit_failure_blocks_smtp_send():
    approval = _approval_branch()
    pending_audit = approval.index('if not audit_event(db, status="pending", **audit_fields):')
    fail_closed = approval.index('raise RuntimeError("Az e-mailt nem küldtem el: az auditnapló nem írható.")')
    smtp_send = approval.index("send_email(")
    assert pending_audit < fail_closed < smtp_send


def test_chat_email_smtp_failure_is_audited_and_reported():
    approval = _approval_branch()
    _call_positions(approval, [
        "send_email(",
        'except Exception as email_exc:',
        'audit_event(\n                                db, status="unknown"',
        "report_error(",
        'operation="send_approved_chat_email"',
    ])
    assert approval.rindex("raise") > approval.index('operation="send_approved_chat_email"')


def test_chat_email_final_audit_failure_warns_against_duplicate_send():
    approval = _approval_branch()
    _call_positions(approval, [
        'audit_saved = audit_event(',
        "if audit_saved:",
        "else:",
        'db, status="unknown"',
        "SMTP átvétel megtörtént, de a záró auditbejegyzés nem menthető.",
        "A küldést ne ismételd meg ellenőrzés nélkül.",
    ])


def test_pending_approval_is_cleared_on_rejection_and_on_any_new_request():
    rejection_start = SOURCE.index('if q in {"elutasítom"')
    rejection_end = SOURCE.index('elif q in {"jóváhagyom"', rejection_start)
    rejection = SOURCE[rejection_start:rejection_end]
    invalidation_start = SOURCE.index("# A pending approval is valid for exactly the next user message.")
    invalidation = SOURCE[invalidation_start:]
    assert rejection.index('_revoke_pending_action(db)') >= 0
    _call_positions(invalidation, [
        "# A pending approval is valid for exactly the next user message.",
        '_revoke_pending_action(db)',
        "requested_task_action = parse_task_command(prompt)",
    ])


def test_task_database_mutation_is_only_invoked_from_approval_branch():
    approval = _approval_branch()
    assert "execute_task_action(" in approval
    assert "approved=True" in approval
    assert "approval=pending_action.get(\"_approval\")" in approval
    assert "execute_task_action(db, task_action, approved=True)" not in _chat_email_draft_branch()
    task_source = (ROOT / "task_actions.py").read_text(encoding="utf-8")
    assert "approved: bool = False" in task_source
    assert "if approved is not True:" in task_source


def test_normal_chat_uses_retrieved_context_and_bounded_recent_history():
    branch = _top_level_prompt_branch()
    source = ast.get_source_segment(SOURCE, branch)
    _call_positions(source, [
        "context, loaded_sources = retrieve_context(db, prompt)",
        "history = format_conversation_history(",
        "max_chars=10000",
        "max_message_chars=3000",
        "answer = generate_text(",
        "BESZÉLGETÉSI ELŐZMÉNY:",
        "FELHASZNÁLÓ KÉRDÉSE: {prompt}",
    ])


def test_empty_model_response_is_treated_as_failure_not_success():
    branch = _top_level_prompt_branch()
    source = ast.get_source_segment(SOURCE, branch)
    normal_start = source.index('else:\n            with st.chat_message("assistant"):')
    normal_chat = source[normal_start:]
    _call_positions(normal_chat, [
        "answer = generate_text(",
        'if not answer:',
        'raise RuntimeError("A Gemini üres választ adott vissza.")',
        'log_event(db, "chat", "chat_response")',
        'st.session_state.chat.append(("assistant", answer))',
    ])


def test_chat_exceptions_are_reported_with_stage_and_sanitized_details():
    branch = _top_level_prompt_branch()
    handlers = [
        node for node in ast.walk(branch)
        if isinstance(node, ast.ExceptHandler)
        and node.name == "exc"
    ]
    assert handlers, "chat request must have an exception boundary"
    handler_source = ast.get_source_segment(SOURCE, handlers[-1])
    assert 'report_error(' in handler_source
    assert 'operation=f"chat_request:{stage}"' in handler_source
    assert "sanitize_log_text(exc, max_length=500)" in handler_source
    assert "chat_error|request_id=" in handler_source


def test_analytics_page_isolated_from_chat_page_execution():
    start = SOURCE.index('if st.session_state.get("jarvis_page") == "analytics":')
    end = SOURCE.index("@st.fragment(run_every", start)
    analytics = SOURCE[start:end]
    _call_positions(analytics, [
        'if st.session_state.get("jarvis_page") == "analytics":',
        "render_analytics(analytics_db)",
        "st.stop()",
    ])
    _call_positions(SOURCE, ["st.stop()", "render_topbar_clock()", 'prompt = st.chat_input('])


def test_diagnostic_shortcut_returns_without_running_normal_chat_pipeline():
    branch = _top_level_prompt_branch()
    source = ast.get_source_segment(SOURCE, branch)
    _call_positions(source, [
        'if prompt.strip().casefold() in {',
        "run_self_diagnostics(**_auth_session_kwargs())",
        'st.session_state.chat.append(("assistant", diagnostic_report))',
        "st.stop()",
        'response_status = st.status(',
    ])
