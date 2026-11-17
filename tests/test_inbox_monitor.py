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
