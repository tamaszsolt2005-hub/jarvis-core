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
        {"company_name": "Engedélyezett Kft.", "approved_to_contact": True, "opted_out": False,
         "next_follow_up_at": "2026-11-14T09:00:00Z"},
        {"company_name": "Nem engedélyezett Kft.", "approved_to_contact": False, "opted_out": False,
         "next_follow_up_at": "2026-11-13T09:00:00Z"},
        {"company_name": "Leiratkozott Kft.", "approved_to_contact": True, "opted_out": True,
         "next_follow_up_at": "2026-11-12T09:00:00Z"},
    ])
    report = build_daily_briefing(db, today=date(2026, 11, 15))
    assert "Lejárt, jóváhagyott utánkövetések: 1" in report
    assert "Engedélyezett Kft." in report
    assert "Nem engedélyezett Kft." not in report
    assert "Leiratkozott Kft." not in report


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
