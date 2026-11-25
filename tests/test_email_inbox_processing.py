from email.message import EmailMessage

import pytest

import email_inbox


class _Result:
    def __init__(self, data=None):
        self.data = data or []


class _Query:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.filters = []
        self.operation = "select"
        self.values = None
        self.negated = False

    @property
    def not_(self):
        self.negated = True
        return self

    def is_(self, key, value):
        if self.negated and value == "null":
            self.negated = False
            return self
        self.filters.append((key, None if value == "null" else value))
        return self

    def select(self, _columns):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, _limit):
        return self

    def update(self, values):
        self.operation = "update"
        self.values = values
        return self

    def upsert(self, values):
        self.operation = "upsert"
        self.values = values
        return self

    def execute(self):
        if self.table_name == "settings":
            if self.operation == "upsert":
                self.db.checkpoint = self.values["value"]
                return _Result()
            return _Result([{"value": self.db.checkpoint}] if self.db.checkpoint else [])
        matches = [
            row for row in self.db.leads
            if all(row.get(key) == value for key, value in self.filters)
        ]
        if self.operation == "update":
            for row in matches:
                row.update(self.values)
            return _Result([{"id": row["id"]} for row in matches])
        return _Result([dict(row) for row in matches])


class _DB:
    def __init__(self, lead):
        self.leads = [lead]
        self.checkpoint = None

    def table(self, name):
        return _Query(self, name)


class _Mailbox:
    def __init__(self, messages):
        self.messages = messages

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def login(self, *_args):
        return "OK", []

    def select(self, *_args, **_kwargs):
        return "OK", []

    def search(self, *_args):
        return "OK", [b"10"]

    def response(self, _name):
        return "UIDVALIDITY", [b"77"]

    def uid(self, command, uid, *_args):
        if command == "search":
            return "OK", [b"10"]
        return "OK", [(b"RFC822", self.messages[uid].as_bytes())]


def _message(sender, subject, body, message_id):
    message = EmailMessage()
    message["From"] = sender
    message["Subject"] = subject
    message["Message-ID"] = message_id
    message.set_content(body)
    return message


def _configure(monkeypatch, db, message, *, audit=True):
    monkeypatch.setattr(email_inbox, "env_bool", lambda _name, default=False: True)
    monkeypatch.setattr(
        email_inbox, "get_secret",
        lambda name, default=None: {"IMAP_HOST": "imap.example.test", "IMAP_PORT": "993"}.get(name, default),
    )
    monkeypatch.setattr(email_inbox, "required_secret", lambda _name: "mock-credential")
    monkeypatch.setattr(email_inbox, "get_service_supabase", lambda: db)
    monkeypatch.setattr(email_inbox.imaplib, "IMAP4_SSL", lambda *_args: _Mailbox({b"10": message}))
    monkeypatch.setattr(email_inbox, "audit_event", lambda *_args, **_kwargs: audit)
    monkeypatch.setattr(email_inbox, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(email_inbox, "report_error", lambda *_args, **_kwargs: None)


def _lead():
    return {
        "id": "lead-1",
        "email": "contact@example.test",
        "status": "sent",
        "opted_out": False,
        "last_inbound_message_id": None,
    }


def test_inbox_reply_updates_lead_and_advances_uid_checkpoint(monkeypatch):
    db = _DB(_lead())
    message = _message("contact@example.test", "Re: ajánlat", "Köszönöm, érdekel.", "<reply-1>")
    _configure(monkeypatch, db, message)

    assert email_inbox._run() == 1

    assert db.leads[0]["status"] == "replied"
    assert db.leads[0]["reply_category"] == "reply"
    assert db.leads[0]["opted_out"] is False
    assert db.leads[0]["next_follow_up_at"] is None
    assert db.checkpoint == {"uidvalidity": "77", "last_uid": 10}


def test_inbox_opt_out_is_sticky_and_stops_follow_up(monkeypatch):
    db = _DB(_lead())
    message = _message("contact@example.test", "Unsubscribe", "Please remove me.", "<reply-2>")
    _configure(monkeypatch, db, message)

    assert email_inbox._run() == 1

    assert db.leads[0]["status"] == "opted_out"
    assert db.leads[0]["reply_category"] == "opt_out"
    assert db.leads[0]["opted_out"] is True
    assert db.leads[0]["next_follow_up_at"] is None
    assert db.checkpoint["last_uid"] == 10


def test_inbox_does_not_change_lead_or_checkpoint_when_pending_audit_fails(monkeypatch):
    db = _DB(_lead())
    message = _message("contact@example.test", "Re: ajánlat", "Köszönöm.", "<reply-3>")
    _configure(monkeypatch, db, message, audit=False)

    with pytest.raises(RuntimeError, match="pending audit"):
        email_inbox._run()

    assert db.leads[0]["last_inbound_message_id"] is None
    assert db.leads[0]["status"] == "sent"
    assert db.checkpoint is None


def test_inbox_decode_and_body_handle_encoded_headers_and_empty_payloads():
    from email.header import Header
    from email.message import EmailMessage

    encoded = Header("Árvíztűrő tükörfúrógép", "utf-8").encode()
    assert email_inbox._decode(None) == ""
    assert email_inbox._decode(encoded) == "Árvíztűrő tükörfúrógép"

    message = EmailMessage()
    message.set_content("Válasz szöveg")
    message.add_attachment(b"binary", maintype="application", subtype="octet-stream", filename="x.bin")
    assert "Válasz szöveg" in email_inbox._body(message)


def test_inbox_uid_checkpoint_invalid_last_uid_fails_back_to_full_bounded_window():
    assert email_inbox._uids_to_process(
        [b"1", b"2", b"3"], {"uidvalidity": "77", "last_uid": "invalid"}, "77"
    ) == [b"1", b"2", b"3"]


def test_inbox_checkpoint_loader_rejects_non_dictionary_value():
    db = _DB(_lead())
    db.checkpoint = ["not", "a", "mapping"]
    assert email_inbox._load_checkpoint(db) == {}


def test_inbox_disabled_and_invalid_port_fail_before_database_access(monkeypatch, capsys):
    monkeypatch.setattr(email_inbox, "env_bool", lambda *_args: False)
    monkeypatch.setattr(email_inbox, "get_service_supabase", lambda: pytest.fail("disabled inbox must not connect"))
    assert email_inbox._run() == 0
    assert "kihagyva" in capsys.readouterr().out

    monkeypatch.setattr(email_inbox, "env_bool", lambda *_args: True)
    monkeypatch.setattr(email_inbox, "get_secret", lambda name, default=None: "70000" if name == "IMAP_PORT" else default)
    with pytest.raises(ValueError, match="IMAP_PORT"):
        email_inbox._run()


def test_inbox_search_or_fetch_failure_never_advances_uid_checkpoint(monkeypatch):
    db = _DB(_lead())
    message = _message("contact@example.test", "Re: ajánlat", "Köszönöm.", "<reply-fail>")
    _configure(monkeypatch, db, message)

    class SearchFailure(_Mailbox):
        def uid(self, command, uid, *_args):
            if command == "search":
                return "NO", []
            return super().uid(command, uid, *_args)
    monkeypatch.setattr(email_inbox.imaplib, "IMAP4_SSL", lambda *_args: SearchFailure({b"10": message}))
    with pytest.raises(RuntimeError, match="keresése sikertelen"):
        email_inbox._run()
    assert db.checkpoint is None

    class FetchFailure(_Mailbox):
        def uid(self, command, uid, *_args):
            if command == "fetch":
                return "NO", []
            return super().uid(command, uid, *_args)
    monkeypatch.setattr(email_inbox.imaplib, "IMAP4_SSL", lambda *_args: FetchFailure({b"10": message}))
    with pytest.raises(RuntimeError, match="UID checkpoint"):
        email_inbox._run()
    assert db.checkpoint is None


@pytest.mark.parametrize("lead_changes", [
    {"email": "other@example.test"},
    {"last_inbound_message_id": "<reply-duplicate>"},
    {"opted_out": True},
])
def test_inbox_skips_unknown_duplicate_or_already_opted_out_sender_and_saves_checkpoint(monkeypatch, lead_changes):
    db = _DB({**_lead(), **lead_changes})
    message = _message("contact@example.test", "Re: ajánlat", "Köszönöm.", "<reply-duplicate>")
    _configure(monkeypatch, db, message)

    assert email_inbox._run() == 0
    assert db.checkpoint == {"uidvalidity": "77", "last_uid": 10}
