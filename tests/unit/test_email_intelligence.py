from types import SimpleNamespace

from packages.integrations.gmail.intelligence import analyze_recruiter_email


def test_interview_email_suggests_state_without_mutating_application():
    application = SimpleNamespace(id=41, role_title="Data Engineer", company_name="Acme Analytics")
    result = analyze_recruiter_email(
        "Interview invitation: Data Engineer at Acme Analytics",
        "We would like to schedule an interview on 2026-11-12 at 10:30 EAT.",
        [application],
    )
    assert result["intent"] == "interview_invitation"
    assert result["suggested_status"] == "interview"
    assert result["application_id"] == 41
    assert result["evidence"]["state_change_requires_candidate_confirmation"] is True
    assert result["interview_proposed_text"] == "2026-11-12 at 10:30 EAT"


def test_ambiguous_email_does_not_link_to_arbitrary_application():
    apps = [
        SimpleNamespace(id=1, role_title="Data Engineer", company_name="Acme"),
        SimpleNamespace(id=2, role_title="Analytics Engineer", company_name="Acme"),
    ]
    result = analyze_recruiter_email(
        "Interview invitation at Acme",
        "We would like to schedule an interview.",
        apps,
    )
    assert result["intent"] == "interview_invitation"
    assert result["application_id"] is None
    assert "ambiguous_application_match" in result["evidence"]["matched_phrases"]


def test_rejection_classification_requires_no_automatic_transition():
    application = SimpleNamespace(id=8, role_title="Platform Engineer", company_name="Example")
    result = analyze_recruiter_email(
        "Update on your application",
        "Unfortunately, we will not be moving forward with your application for Platform Engineer.",
        [application],
    )
    assert result["suggested_status"] == "rejected"
    assert result["application_id"] == 8
    assert result["evidence"]["state_change_requires_candidate_confirmation"] is True
