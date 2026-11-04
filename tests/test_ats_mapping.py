from packages.automation.ats_mapping import build_mapping, approval_manifest, resolve_field

def test_exact_alias_mapping_and_unknown_review():
    rows = build_mapping(
        [{"id": "email-1", "label": "Email Address"},
         {"id": "custom-1", "label": "Why should we hire you?"}],
        {"email": "candidate@example.com"},
    )
    assert rows[0].status == "proposed"
    assert rows[0].value == "candidate@example.com"
    assert rows[1].status == "needs_review"

def test_approval_requires_confirmation_and_complete_exact_mapping():
    rows = build_mapping([{"id": "name", "label": "Full Name"}], {"full_name": "Candidate"})
    assert approval_manifest(12, rows, False)["approved"] is False
    assert approval_manifest(12, rows, True)["approved"] is True

def test_unknown_fields_never_get_fuzzy_mapped():
    assert resolve_field("Tell us your life story") is None
