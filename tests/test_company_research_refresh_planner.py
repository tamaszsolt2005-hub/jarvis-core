from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from company_research_refresh_planner import plan_company_research_refresh_candidates

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def lead(status="new", **extra):
    return {
        "id": str(uuid4()),
        "company_name": "Example Ltd",
        "website": "https://www.example.com",
        "status": status,
        **extra,
    }


def dossier(researched_at):
    return {"researched_at": researched_at.isoformat()}


def test_planner_prioritizes_uncontacted_stale_leads_before_contacted_ones():
    uncontacted = lead()
    contacted = lead("sent", last_outbound_at="2026-10-01T10:00:00+00:00")
    rows = plan_company_research_refresh_candidates(
        [contacted, uncontacted],
        {
            contacted["id"]: dossier(NOW - timedelta(days=60)),
            uncontacted["id"]: dossier(NOW - timedelta(days=31)),
        },
        now=NOW,
    )
    assert [row["lead_id"] for row in rows] == [uncontacted["id"], contacted["id"]]
    assert rows[0]["priority"] == "uncontacted"
    assert rows[1]["priority"] == "existing_relationship"


def test_planner_includes_uncontacted_leads_without_any_dossier():
    item = lead()
    rows = plan_company_research_refresh_candidates([item], {}, now=NOW)
    assert len(rows) == 1
    assert rows[0]["reason"] == "missing_dossier"


def test_planner_excludes_fresh_dossiers():
    item = lead()
    rows = plan_company_research_refresh_candidates(
        [item], {item["id"]: dossier(NOW - timedelta(days=10))}, now=NOW
    )
    assert rows == []


@pytest.mark.parametrize("item", [
    lead("rejected"),
    lead("not_interested"),
    lead("opted_out"),
    lead("do_not_contact"),
    lead("follow_up_sent", follow_up_count=2),
])
def test_planner_excludes_rejected_opted_out_and_unanswered_followup_limit(item):
    rows = plan_company_research_refresh_candidates([item], {}, now=NOW)
    assert rows == []


def test_planner_keeps_replied_company_eligible_for_research_review():
    item = lead("replied", reply_category="interested", follow_up_count=3)
    rows = plan_company_research_refresh_candidates([item], {}, now=NOW)
    assert len(rows) == 1
    assert rows[0]["priority"] == "existing_relationship"


def test_inbound_reply_is_never_prioritized_as_uncontacted():
    item = lead("research", reply_category="interested")
    rows = plan_company_research_refresh_candidates([item], {}, now=NOW)
    assert rows[0]["priority"] == "existing_relationship"


@pytest.mark.parametrize("website", [
    "ftp://example.com", "https:///missing-host", "https://bad..domain",
    "https://localhost/path",
])
def test_planner_rejects_non_http_or_malformed_domains(website):
    item = lead(website=website)
    assert plan_company_research_refresh_candidates([item], {}, now=NOW) == []


def test_planner_deduplicates_lead_ids_and_respects_limit():
    first = lead()
    second = lead()
    rows = plan_company_research_refresh_candidates(
        [first, first, second], {}, now=NOW, limit=1
    )
    assert len(rows) == 1
    assert rows[0]["lead_id"] in {first["id"], second["id"]}


def test_planner_skips_records_without_valid_company_domain():
    item = {"id": str(uuid4()), "company_name": "No website"}
    assert plan_company_research_refresh_candidates([item], {}, now=NOW) == []


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_planner_validates_limit(limit):
    with pytest.raises(ValueError, match="limit"):
        plan_company_research_refresh_candidates([], {}, now=NOW, limit=limit)


@pytest.mark.parametrize("age", [-1, True, 1.5])
def test_planner_validates_max_age(age):
    with pytest.raises(ValueError, match="max_age_days"):
        plan_company_research_refresh_candidates([], {}, now=NOW, max_age_days=age)


def test_planner_requires_timezone_aware_now():
    with pytest.raises(ValueError, match="timezone-aware"):
        plan_company_research_refresh_candidates([], {}, now=datetime(2026, 11, 26))



def test_planner_treats_snapshot_row_without_dossier_payload_as_missing():
    item = lead()
    rows = plan_company_research_refresh_candidates(
        [item],
        {item["id"]: {"researched_at": (NOW - timedelta(days=1)).isoformat(), "dossier": None}},
        now=NOW,
    )
    assert len(rows) == 1
    assert rows[0]["reason"] == "missing_dossier"


@pytest.mark.parametrize("marker", [
    {"first_sent_at": "2026-11-01T10:00:00+00:00"},
    {"followed_up_at": "2026-11-02T10:00:00+00:00"},
    {"last_message_id": "outbound-message-1"},
])
def test_planner_does_not_misclassify_legacy_contacted_leads_as_uncontacted(marker):
    item = lead("new", **marker)
    rows = plan_company_research_refresh_candidates([item], {}, now=NOW)
    assert rows[0]["priority"] == "existing_relationship"
