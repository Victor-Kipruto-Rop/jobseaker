from packages.applications.email_intent import classify_email

def test_interview_email_is_evidence_only():
    result = classify_email("Interview invitation", "Please schedule an interview.")
    assert result["intent"] == "interview"
    assert result["state_change_permitted"] is False

def test_unknown_email_is_not_guessed():
    result = classify_email("Hello", "Please read our newsletter.")
    assert result["intent"] == "unknown"

def test_conflicting_email_requires_review():
    result = classify_email("Update", "Offer interview, but unfortunately cannot proceed.")
    assert result["requires_review"] is True
