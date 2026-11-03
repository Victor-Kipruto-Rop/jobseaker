from apps.api.app.api.v1.applications.routes import TRANSITIONS

def test_application_requires_approval_before_submission():
    assert "submitted" not in TRANSITIONS["draft"]
    assert "submitted" in TRANSITIONS["approved"]

def test_offer_can_be_accepted_or_rejected():
    assert TRANSITIONS["offer"] == {"accepted", "rejected", "withdrawn"}

def test_closed_application_cannot_be_reopened():
    assert TRANSITIONS["archived"] == set()
