from email.message import EmailMessage

from inbox_monitor import _body, _decode, _pending_messages


def _message(message_id, body="válasz"):
    msg = EmailMessage()
    msg["Message-ID"] = message_id
    msg["From"] = "contact@example.com"
    msg.set_content(body)
    return msg


def test_pending_messages_returns_all_messages_after_marker_in_chronological_order():
    messages = [
        (b"1", _message("<one>")),
        (b"2", _message("<two>")),
        (b"3", _message("<three>")),
        (b"4", _message("<four>")),
    ]
    pending = _pending_messages(messages, "<two>")
    assert [msg["Message-ID"] for _, msg in pending] == ["<three>", "<four>"]


def test_pending_messages_without_marker_only_returns_newest_bounded_message():
    messages = [(b"1", _message("<one>")), (b"2", _message("<two>"))]
    pending = _pending_messages(messages, "<outside-window>")
    assert [msg["Message-ID"] for _, msg in pending] == ["<two>"]


def test_pending_messages_without_previous_marker_returns_all_messages():
    messages = [(b"1", _message("<one>")), (b"2", _message("<two>"))]
    assert len(_pending_messages(messages, None)) == 2


def test_inbox_body_ignores_attachments_and_decodes_text():
    msg = EmailMessage()
    msg.set_content("Érdekel az ajánlat.")
    msg.add_attachment(b"secret", maintype="application", subtype="octet-stream", filename="x.bin")
    assert "Érdekel az ajánlat." in _body(msg)
    assert "secret" not in _body(msg)


def test_header_decode_handles_plain_unicode():
    assert _decode("Egyszerű tárgy") == "Egyszerű tárgy"



def test_opt_out_is_sticky_when_processing_multiple_new_replies():
    # A later positive message must never revoke an earlier explicit opt-out.
    opted_out = False
    for category in ("opt_out", "interested"):
        opted_out = opted_out or category == "opt_out"
    assert opted_out is True



def test_run_processes_new_replies_in_order_and_never_clears_opt_out(monkeypatch):
    import inbox_monitor

    lead = {
        "id": "lead-1",
        "email": "contact@example.com",
        "company_name": "Példa Kft.",
        "status": "sent",
        "last_inbound_message_id": "<one>",
        "opted_out": False,
    }
    updates = []

    class Result:
        def __init__(self, data=None):
            self.data = data or []

    class Query:
        def __init__(self):
            self.update_data = None

        def select(self, _columns):
            return self

        def in_(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def update(self, data):
            self.update_data = data
            updates.append(data)
            return self

        def eq(self, *_args):
            return self

        def execute(self):
            return Result([lead] if self.update_data is None else [])

    class DB:
        def table(self, _name):
            return Query()

    class Mail:
        def login(self, *_args):
            pass

        def select(self, *_args):
            pass

        def search(self, *_args):
            return "OK", [b"1 2 3"]

        def fetch(self, sequence_id, *_args):
            index = int(sequence_id)
            msg = _message(f"<{['zero', 'one', 'two', 'three'][index]}>",
                           "unsubscribe" if index == 2 else "interested")
            return "OK", [(b"RFC822", msg.as_bytes())]

        def logout(self):
            pass

    monkeypatch.setattr(inbox_monitor, "get_secret", lambda name, default=None: {
        "EMAIL_USER": "sender@example.com",
        "EMAIL_PASSWORD": "test-only",
        "IMAP_HOST": "imap.example.com",
        "IMAP_PORT": "993",
    }.get(name, default))
    monkeypatch.setattr(inbox_monitor, "get_supabase", lambda: DB())
    monkeypatch.setattr(inbox_monitor.imaplib, "IMAP4_SSL", lambda *_args: Mail())
    monkeypatch.setattr(
        inbox_monitor, "classify_reply",
        lambda body: "opt_out" if "unsubscribe" in body else "interested",
    )
    monkeypatch.setattr(inbox_monitor, "log_event", lambda *_args: None)

    inbox_monitor.run()

    assert len(updates) == 2
    assert updates[0]["opted_out"] is True
    assert updates[1]["opted_out"] is True
    assert updates[1]["status"] == "opted_out"
    assert updates[1]["reply_category"] == "opt_out"
    assert updates[1]["last_inbound_message_id"] == "<three>"


def test_inbox_helpers_handle_missing_headers_empty_payload_and_duplicate_markers():
    from email.message import EmailMessage
    from email.header import Header

    assert _decode(None) == ""
    encoded = Header("Árvíztűrő tükörfúrógép", "utf-8").encode()
    assert _decode(encoded) == "Árvíztűrő tükörfúrógép"
    assert _pending_messages(None, None) == []

    empty = EmailMessage()
    empty.set_type("multipart/mixed")
    assert _body(empty) == ""

    messages = [
        (b"1", _message("<marker>")),
        (b"2", _message("<middle>")),
        (b"3", _message("<marker>")),
        (b"4", _message("<newest>")),
    ]
    assert [msg["Message-ID"] for _, msg in _pending_messages(messages, "<marker>")] == ["<newest>"]


def test_inbox_monitor_skips_when_credentials_are_missing(monkeypatch, capsys):
    import inbox_monitor

    monkeypatch.setattr(inbox_monitor, "get_secret", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(inbox_monitor, "get_supabase", lambda: (_ for _ in ()).throw(AssertionError("must not connect")))
    assert inbox_monitor._run() is None
    assert "hiányzik" in capsys.readouterr().out


def test_inbox_monitor_run_reports_and_reraises_worker_failure(monkeypatch):
    import pytest
    import inbox_monitor

    failure = ConnectionError("mock IMAP outage")
    reports = []
    monkeypatch.setattr(
        inbox_monitor, "_run",
        lambda: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        inbox_monitor, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )
    with pytest.raises(ConnectionError, match="mock IMAP outage"):
        inbox_monitor.run()
    assert reports[0][0] is failure
    assert reports[0][1]["operation"] == "process_inbox_monitor"
    assert reports[0][1]["severity"] == "error"
