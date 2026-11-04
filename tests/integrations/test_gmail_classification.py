from packages.integrations.gmail.client import classify


def test_interview_email_is_flagged_for_action():
    category, confidence, action = classify(
        "Interview invitation", "Please choose a time for your interview"
    )
    assert category == "interview_invitation"
    assert confidence >= 0.7
    assert action is True


def test_application_acknowledgement_is_not_action_required():
    category, _, action = classify("Application received", "Thank you for applying")
    assert category == "acknowledgement"
    assert action is False


def test_unclassified_mail_is_not_assumed_to_need_action():
    category, confidence, action = classify("Hello", "Just sharing an update")
    assert category == "unclassified_job_related"
    assert confidence < 0.5
    assert action is False
