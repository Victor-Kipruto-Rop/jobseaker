import pytest

from packages.automation.form_assist import (
    FormFieldDescriptor, build_form_fill_plan,
)


def test_form_plan_only_uses_verbatim_candidate_facts_and_high_confidence():
    fields = [
        FormFieldDescriptor(label="Full name", field_type="text", required=True),
        FormFieldDescriptor(label="Email", field_type="email", required=True),
        FormFieldDescriptor(label="Portfolio", field_type="url", required=False),
    ]
    profile = {"full_name": "Victor Kipruto", "email": "victor@example.com"}
    def mapper(descriptors, candidate):
        return {
            "mappings": [
                {"label": "Full name", "value": candidate["full_name"],
                 "source_field": "full_name", "confidence": 0.99},
                {"label": "Email", "value": candidate["email"],
                 "source_field": "email", "confidence": 0.70},
            ],
            "unresolved_required": [], "approval_required": True, "can_submit": False,
        }
    plan = build_form_fill_plan(fields, profile, mapper)
    assert [item.label for item in plan.mappings] == ["Full name"]
    assert plan.unresolved_required == ["Email"]
    assert plan.approval_required is True
    assert plan.can_submit is False


def test_form_plan_rejects_fabricated_candidate_values():
    fields = [FormFieldDescriptor(label="Full name", field_type="text", required=True)]
    def mapper(descriptors, candidate):
        return {
            "mappings": [{
                "label": "Full name", "value": "Invented Person",
                "source_field": "full_name", "confidence": 0.99,
            }],
            "unresolved_required": [], "approval_required": True, "can_submit": False,
        }
    with pytest.raises(ValueError, match="changed candidate-supplied facts"):
        build_form_fill_plan(fields, {"full_name": "Victor Kipruto"}, mapper)


def test_form_plan_rejects_unpublished_select_option():
    fields = [FormFieldDescriptor(
        label="Work authorization", field_type="select",
        options=["Yes", "No"], required=True,
    )]
    def mapper(descriptors, candidate):
        return {
            "mappings": [{
                "label": "Work authorization", "value": "Maybe",
                "source_field": "work_authorization", "confidence": 0.99,
            }],
            "unresolved_required": [], "approval_required": True, "can_submit": False,
        }
    with pytest.raises(ValueError, match="not one of the options"):
        build_form_fill_plan(fields, {"work_authorization": "Maybe"}, mapper)
