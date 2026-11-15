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
