from app.email_intelligence.gmail import classify_message


def test_interview_email_requires_action():
    category, confidence, action, evidence = classify_message(
        "Interview invitation", "We would like to schedule an interview next week."
    )
    assert category == "interview_invitation"
    assert confidence > 0
    assert action is True
    assert evidence == "interview"


def test_silence_is_not_a_rejection():
    category, _, action, _ = classify_message("Following up", "Just checking in.")
    assert category == "unclassified_job_related"
    assert action is False


def test_rejection_is_classified():
    category, _, _, _ = classify_message(
        "Application update", "Unfortunately, we will not be moving forward."
    )
    assert category == "rejection"
