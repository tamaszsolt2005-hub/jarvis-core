from datetime import date

from daily_briefing import build_daily_briefing


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table

    def select(self, _columns):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        return Result(self.db.rows.get(self.table, []))


class FakeDB:
    def __init__(self):
        self.rows = {
            "leads": [{
                "id": "lead-example-1",
                "company_name": "Példa Kft.", "website": "https://example.com",
                "status": "research", "source": "gemini_google_search_grounding:example.com",
                "created_at": "2026-11-15T06:00:00Z",
                "notes": "Leadkutatás; tényleges ország: Hungary; iparág: Manufacturing. "
                         "AI üzleti illeszkedési becslés: 80/100; bizonyosság: high; "
                         "alátámasztó jelek: nyilvános termékoldal; esettanulmány; "
                         "javasolt kutatási lépés: ellenőrzés",
            }],
            "tasks": [{"title": "Ajánlat ellenőrzése", "status": "open", "priority": "high",
                       "due_at": "2026-11-14T10:00:00Z"}],
        }

    def table(self, name):
        return Query(self, name)


def test_daily_briefing_contains_priority_and_overdue_task():
    report = build_daily_briefing(FakeDB(), today=date(2026, 11, 15))
    assert "Példa Kft." in report
    assert "Ajánlat ellenőrzése" in report
    assert "Lejárt feladatok: 1" in report
    assert "Kiemelt nyitott feladatok" in report
    assert "nem vásárlási szándék" in report


def test_daily_briefing_builds_action_plan_from_overdue_task_and_top_lead():
    report = build_daily_briefing(FakeDB(), today=date(2026, 11, 15))
    assert "Javasolt napi akcióterv" in report
    assert "Rendezd a lejárt feladatot" in report
    assert "Ellenőrizd a legmagasabb kutatási prioritású céget" in report

def test_daily_briefing_adds_evidence_based_lead_task_proposal_without_writing():
    db = FakeDB()
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    assert "Következő belső feladatjavaslatok" in report
    assert "Üzleti igény és szolgáltatási illeszkedés ellenőrzése – Példa Kft." in report
    assert "lead-example-1" in report
    assert "kapcsolatfelvételi engedély" in report
    assert db.rows["leads"][0]["status"] == "research"
    assert db.rows["tasks"][0]["title"] == "Ajánlat ellenőrzése"


def test_daily_briefing_does_not_repeat_task_proposal_for_linked_lead():
    db = FakeDB()
    db.rows["tasks"].append({
        "id": "task-linked", "lead_id": "lead-example-1",
        "title": "Kutatás ellenőrzése", "status": "open", "priority": "normal",
    })
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    assert "Nincs olyan strukturált kutatási lead, amelyhez még ne tartozna feladat." in report
    assert "Üzleti igény és szolgáltatási illeszkedés ellenőrzése – Példa Kft." not in report


def test_daily_briefing_prioritizes_urgent_overdue_tasks():
    db = FakeDB()
    db.rows["tasks"].append({"title": "Sürgős szerződés", "status": "open", "priority": "urgent",
                             "due_at": "2026-11-13T10:00:00Z"})
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    action_section = report.split("## Javasolt napi akcióterv", 1)[1]
    assert action_section.index("Sürgős szerződés") < action_section.index("Ajánlat ellenőrzése")


def test_daily_briefing_only_flags_overdue_followups_with_explicit_approval():
    db = FakeDB()
    db.rows["leads"].extend([
        {"company_name": "Engedélyezett Kft.", "status": "sent", "email": "ok@example.test",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-13T09:00:00Z",
         "approved_to_contact": True, "opted_out": False, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 0,
         "next_follow_up_at": "2026-11-14T09:00:00Z"},
        {"company_name": "Nem engedélyezett Kft.", "status": "sent", "email": "no@example.test",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-13T09:00:00Z",
         "approved_to_contact": False, "opted_out": False, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 0,
         "next_follow_up_at": "2026-11-13T09:00:00Z"},
        {"company_name": "Leiratkozott Kft.", "status": "sent", "email": "out@example.test",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-13T09:00:00Z",
         "approved_to_contact": True, "opted_out": True, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 0,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
        {"company_name": "Válaszolt Kft.", "status": "sent", "email": "reply@example.test",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-13T09:00:00Z",
         "approved_to_contact": True, "opted_out": False, "reply_category": "reply",
         "last_inbound_message_id": "<reply>", "follow_up_count": 0,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
        {"company_name": "Hozzájárulás nélküli Kft.", "status": "sent", "email": "none@example.test",
         "consent_basis": None, "consent_confirmed_at": None,
         "approved_to_contact": True, "opted_out": False, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 0,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
        {"company_name": "Jövőbeli hozzájárulású Kft.", "status": "sent", "email": "future@example.test",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-24T09:00:00Z",
         "approved_to_contact": True, "opted_out": False, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 0,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
        {"company_name": "Már utánkövetett Kft.", "status": "sent", "email": "done@example.test",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-13T09:00:00Z",
         "approved_to_contact": True, "opted_out": False, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 1,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
        {"company_name": "Új lead", "status": "new", "email": "new@example.test",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-13T09:00:00Z",
         "approved_to_contact": True, "opted_out": False, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 0,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
        {"company_name": "Hibás e-mail", "status": "sent", "email": "bad-address",
         "consent_basis": "consent", "consent_confirmed_at": "2026-11-13T09:00:00Z",
         "approved_to_contact": True, "opted_out": False, "reply_category": None,
         "last_inbound_message_id": None, "follow_up_count": 0,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
    ])
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    assert "Lejárt, jóváhagyott utánkövetések: 1" in report
    assert "Engedélyezett Kft." in report
    assert "Nem engedélyezett Kft." not in report
    assert "Leiratkozott Kft." not in report
    assert "Válaszolt Kft." not in report
    assert "Hozzájárulás nélküli Kft." not in report
    assert "Jövőbeli hozzájárulású Kft." not in report
    assert "Már utánkövetett Kft." not in report
    assert "Új lead" not in report
    assert "Hibás e-mail" not in report


def test_deadlines_are_compared_using_budapest_local_date():
    db = FakeDB()
    db.rows["tasks"].append({"title": "Éjféli határidő", "status": "open", "priority": "normal",
                             "due_at": "2026-11-14T23:00:00Z"})
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    assert "Lejárt feladatok: 1" in report
    assert "Ma esedékes feladatok: 1" in report
    assert "Éjféli határidő" in report



def test_daily_briefing_includes_high_priority_task_without_deadline_in_action_plan():
    db = FakeDB()
    db.rows["tasks"].append({
        "title": "Piaci ajánlat kidolgozása",
        "status": "open",
        "priority": "high",
        "due_at": None,
    })
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    assert "Haladj a magas prioritású feladattal" in report
    assert "Piaci ajánlat kidolgozása" in report
    assert "## Vezetői fókusz" in report


def test_daily_briefing_uses_budapest_date_for_new_companies():
    db = FakeDB()
    db.rows["leads"].append({
        "company_name": "Éjfél után létrejött Kft.",
        "created_at": "2026-11-14T23:30:00Z",
        "status": "research",
    })
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    assert "Éjfél után létrejött Kft." in report



def test_daily_briefing_falls_back_when_legacy_schema_lacks_website_column():
    class MissingWebsiteQuery(Query):
        def select(self, columns):
            if "website" in columns:
                raise RuntimeError("column leads.website does not exist")
            return self

    class MissingWebsiteDB(FakeDB):
        def table(self, name):
            if name == "leads":
                return MissingWebsiteQuery(self, name)
            return super().table(name)

    report = build_daily_briefing(MissingWebsiteDB(), today=date(2026, 11, 15))
    assert "JARVIS – napi vezetői jelentés" in report
    assert "Adatbázis-séma figyelmeztetés" in report
    assert "website" in report


def test_local_date_handles_missing_invalid_naive_and_utc_values():
    from daily_briefing import _local_date

    assert _local_date(None) is None
    assert _local_date("not-a-date") is None
    assert _local_date("2026-11-15T01:00:00") == date(2026, 11, 15)
    assert _local_date("2026-11-14T23:30:00Z") == date(2026, 11, 15)


def test_daily_briefing_empty_data_uses_truthful_empty_states():
    class EmptyDB:
        def table(self, _name):
            class EmptyQuery(Query):
                def execute(self):
                    return Result([])
            return EmptyQuery(self, _name)

    report = build_daily_briefing(EmptyDB(), today=date(2026, 11, 15))

    assert "Vizsgált cégek (legfeljebb 1500): 0" in report
    assert "Még nincs elegendő strukturált kutatási adat" in report
    assert "Nincs sürgős vagy magas prioritású" in report
    assert "Nincs rögzített lejárt" in report
    assert "Nincs mára határidőzött" in report
    assert "Ma még nem került új cég" in report
    assert "Nincs sürgős, határidős feladat" in report


def test_daily_briefing_propagates_non_schema_database_errors():
    class BrokenQuery(Query):
        def execute(self):
            raise RuntimeError("mock database outage")

    class BrokenDB:
        def table(self, name):
            return BrokenQuery(self, name)

    import pytest
    with pytest.raises(RuntimeError, match="mock database outage"):
        build_daily_briefing(BrokenDB(), today=date(2026, 11, 15))


def test_daily_briefing_main_writes_report_and_appends_monitor(monkeypatch, tmp_path, capsys):
    import jarvis_common
    import proactive_monitor
    import daily_briefing

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jarvis_common, "get_service_supabase", lambda: FakeDB())
    monkeypatch.setattr(daily_briefing, "build_daily_briefing", lambda _db: "# Daily report")
    monkeypatch.setattr(proactive_monitor, "run_proactive_monitor", lambda _db: "## Monitor\n- No changes")

    daily_briefing.main()

    output = (tmp_path / "daily_briefing.md").read_text(encoding="utf-8")
    assert output == "# Daily report\n## Monitor\n- No changes"
    assert output in capsys.readouterr().out


def test_daily_briefing_main_keeps_report_when_monitor_fails(monkeypatch, tmp_path):
    import jarvis_common
    import proactive_monitor
    import daily_briefing

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jarvis_common, "get_service_supabase", lambda: FakeDB())
    monkeypatch.setattr(daily_briefing, "build_daily_briefing", lambda _db: "# Daily report")
    monkeypatch.setattr(
        proactive_monitor, "run_proactive_monitor",
        lambda _db: (_ for _ in ()).throw(RuntimeError("mock monitor failure")),
    )

    daily_briefing.main()

    output = (tmp_path / "daily_briefing.md").read_text(encoding="utf-8")
    assert "# Daily report" in output
    assert "Proaktív változásfigyelés" in output
    assert "RuntimeError" in output


def test_daily_briefing_main_reports_and_reraises_build_failure(monkeypatch, tmp_path):
    import jarvis_common
    import daily_briefing
    import pytest

    failure = RuntimeError("mock report build failure")
    reports = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jarvis_common, "get_service_supabase", lambda: FakeDB())
    monkeypatch.setattr(
        daily_briefing, "build_daily_briefing",
        lambda _db: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        daily_briefing, "report_error",
        lambda error, **kwargs: reports.append((error, kwargs)),
    )

    with pytest.raises(RuntimeError) as caught:
        daily_briefing.main()

    assert caught.value is failure
    assert reports[0][1]["module"] == "daily_briefing"
    assert reports[0][1]["operation"] == "build_report"
    assert not (tmp_path / "daily_briefing.md").exists()
