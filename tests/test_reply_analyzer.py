from reply_analyzer import fallback_classification

def test_unsubscribe_is_rejected():
    assert fallback_classification("Kérem, iratkoztassanak le.") == "opt_out"

def test_negative_reply_is_rejected():
    assert fallback_classification("Köszönöm, nem érdekel.") == "rejected"

def test_positive_reply_is_interested():
    assert fallback_classification("Érdekel az árajánlat.") == "interested"

def test_later_reply_is_later():
    assert fallback_classification("Keressenek inkább jövő hónapban.") == "later"

def test_unknown_reply_is_unknown():
    assert fallback_classification("Köszönöm az üzenetet.") == "unknown"
