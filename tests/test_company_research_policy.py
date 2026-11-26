import pytest

from company_research_policy import company_research_refresh_decision


@pytest.mark.parametrize("lead", [
    {"status": "rejected"},
    {"status": "not_interested"},
    {"status": "opted_out"},
    {"status": "do_not_contact"},
    {"status": "closed_lost"},
    {"reply_category": "rejected"},
    {"reply_category": "not_interested"},
    {"reply_category": "negative"},
    {"reply_category": "opt_out"},
    {"reply_category": "unsubscribe"},
    {"opted_out": True},
])
def test_explicit_rejection_or_opt_out_suppresses_company_refresh(lead):
    decision = company_research_refresh_decision(lead)
    assert decision["eligible"] is False
    assert decision["reason"] == "explicit_rejection_or_opt_out"


def test_uncontacted_lead_remains_eligible_even_without_contact_permission():
    decision = company_research_refresh_decision({"status": "research", "follow_up_count": 0})
    assert decision["eligible"] is True
    assert decision["reason"] == "eligible_for_research_refresh"


def test_new_lead_remains_eligible():
    assert company_research_refresh_decision({"status": "new"})["eligible"] is True


def test_one_unanswered_followup_does_not_suppress_refresh():
    decision = company_research_refresh_decision({
        "status": "follow_up_sent", "follow_up_count": 1,
    })
    assert decision["eligible"] is True


def test_two_unanswered_followups_pause_automatic_refresh():
    decision = company_research_refresh_decision({
        "status": "follow_up_sent", "follow_up_count": 2,
    })
    assert decision["eligible"] is False
    assert decision["reason"] == "unanswered_follow_up_limit_reached"


def test_inbound_reply_is_not_mislabeled_as_silence():
    decision = company_research_refresh_decision({
        "status": "sent", "follow_up_count": 4,
        "reply_category": "reply", "last_inbound_message_id": "<message>",
    })
    assert decision["eligible"] is True


def test_explicitly_interested_reply_remains_eligible():
    decision = company_research_refresh_decision({
        "status": "replied", "follow_up_count": 4, "reply_category": "interested",
    })
    assert decision["eligible"] is True


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2"])
def test_followup_threshold_must_be_positive_integer(limit):
    with pytest.raises(ValueError):
        company_research_refresh_decision({}, max_unanswered_followups=limit)


def test_malformed_followup_count_does_not_suppress_company():
    decision = company_research_refresh_decision({
        "status": "follow_up_sent", "follow_up_count": "unknown",
    })
    assert decision["eligible"] is True



@pytest.mark.parametrize("status", ["contacted", "no_response", "follow_up_due", "followup_due"])
def test_two_unanswered_followups_pause_refresh_for_contacted_statuses(status):
    decision = company_research_refresh_decision({
        "status": status, "follow_up_count": 2,
    })
    assert decision["eligible"] is False
    assert decision["reason"] == "unanswered_follow_up_limit_reached"
