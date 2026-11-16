from decision_support import decision_support_instructions


def test_decision_request_gets_evidence_led_challenge_framework():
    guidance = decision_support_instructions("Szerinted érdemes Németországban terjeszkedni?")
    assert "ne csak megerősítsd" in guidance
    assert "érdemi alternatívát" in guidance
    assert "sikerkritériummal" in guidance
    assert "bizonyossági szintet" in guidance


def test_ordinary_fact_question_does_not_get_decision_framework():
    assert decision_support_instructions("Hány nyitott feladatom van?") == ""


def test_ascii_hungarian_variant_is_detected():
    guidance = decision_support_instructions("Melyik strategia eri meg jobban?")
    assert guidance
    assert "ellenérvet" in guidance
