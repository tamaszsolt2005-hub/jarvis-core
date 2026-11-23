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

    @property
    def not_(self):
        return self

    def is_(self, key, value):
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
    monkeypatch.setattr(email_inbox, "get_supabase", lambda: db)
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


def test_inbox_does_not_advance_checkpoint_when_audit_write_fails(monkeypatch):
    db = _DB(_lead())
    message = _message("contact@example.test", "Re: ajánlat", "Köszönöm.", "<reply-3>")
    _configure(monkeypatch, db, message, audit=False)

    with pytest.raises(RuntimeError, match="auditnapló"):
        email_inbox._run()

    # Lead state is already updated; retry is idempotent via last_inbound_message_id.
    assert db.leads[0]["last_inbound_message_id"] == "<reply-3>"
    assert db.checkpoint is None
