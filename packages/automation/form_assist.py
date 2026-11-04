"""Candidate-approved ATS form mapping and safe Playwright assistance.

No CAPTCHA solving, fingerprint evasion, proxy rotation, hidden-field manipulation,
or automatic submit action is provided. The caller must obtain explicit approval
for each generated fill plan before applying it.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class FormFieldDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=300)
    field_type: Literal["text", "email", "tel", "url", "textarea", "select", "checkbox"]
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)
    autocomplete: str = Field(default="", max_length=120)


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=300)
    value: str | bool
    source_field: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=500)


class FormFillPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mappings: list[FieldMapping] = Field(default_factory=list, max_length=100)
    unresolved_required: list[str] = Field(default_factory=list, max_length=100)
    approval_required: bool = True
    can_submit: Literal[False] = False


class FormAssistResult(BaseModel):
    status: Literal["filled", "paused_for_human", "approval_required"]
    filled_fields: int = 0
    unresolved_fields: list[str] = Field(default_factory=list)
    reason: str = ""


def build_form_fill_plan(
    fields: list[FormFieldDescriptor],
    candidate_profile: dict[str, Any],
    structured_mapper: Callable[[list[dict], dict], dict],
) -> FormFillPlan:
    """Validate LLM-produced structured mappings against known candidate data."""
    allowed = {
        key: str(value)[:4000] for key, value in candidate_profile.items()
        if isinstance(value, (str, int, float)) and str(value).strip()
    }
    raw = structured_mapper([field.model_dump() for field in fields], allowed)
    plan = FormFillPlan.model_validate(raw)
    field_by_label = {field.label.casefold(): field for field in fields}
    approved = []
    unresolved = {field.label for field in fields if field.required}
    for mapping in plan.mappings:
        descriptor = field_by_label.get(mapping.label.casefold())
        if descriptor is None:
            raise ValueError("Mapper referenced a field that was not present in the inspected form")
        if mapping.source_field not in allowed:
            raise ValueError("Mapper referenced candidate information not supplied in the profile")
        if isinstance(mapping.value, str) and mapping.value != allowed[mapping.source_field]:
            raise ValueError("Mapper changed candidate-supplied facts; values must be copied verbatim")
        if isinstance(mapping.value, bool) and descriptor.field_type != "checkbox":
            raise ValueError("Boolean values are only supported for checkbox fields")
        if descriptor.field_type == "select" and mapping.value not in descriptor.options:
            raise ValueError("Select answer is not one of the options published by the form")
        if descriptor.field_type == "checkbox" and not isinstance(mapping.value, bool):
            raise ValueError("Checkbox answers must be boolean")
        if mapping.confidence >= 0.85:
            approved.append(mapping)
            unresolved.discard(descriptor.label)
    return FormFillPlan(
        mappings=approved,
        unresolved_required=sorted(unresolved),
        approval_required=True,
        can_submit=False,
    )


async def _verification_required(page: Any) -> bool:
    selectors = (
        'iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]',
        '[data-sitekey]', 'input[name*="captcha" i]',
        'iframe[title*="challenge" i]',
    )
    for selector in selectors:
        try:
            if await page.locator(selector).count():
                return True
        except Exception:
            continue
    return False


async def apply_approved_form_plan(
    page: Any, plan: FormFillPlan, *, candidate_approved: bool,
) -> FormAssistResult:
    """Fill high-confidence fields after explicit approval; never submits the form."""
    if not candidate_approved:
        return FormAssistResult(status="approval_required", reason="Candidate approval is required")
    if await _verification_required(page):
        return FormAssistResult(
            status="paused_for_human",
            unresolved_fields=plan.unresolved_required,
            reason="The ATS requires a verification or challenge step; complete it manually",
        )
    filled = 0
    unresolved = set(plan.unresolved_required)
    for mapping in plan.mappings:
        if mapping.confidence < 0.85:
            unresolved.add(mapping.label)
            continue
        locator = page.get_by_label(mapping.label, exact=True)
        if await locator.count() != 1:
            unresolved.add(mapping.label)
            continue
        if isinstance(mapping.value, bool):
            await locator.set_checked(mapping.value)
        else:
            await locator.fill(mapping.value)
        filled += 1
    return FormAssistResult(
        status="filled" if filled else "approval_required",
        filled_fields=filled,
        unresolved_fields=sorted(unresolved),
        reason="Review every populated field and submit manually on the ATS website",
    )


async def capture_failure_evidence(page: Any, *, owner_scope: str) -> dict[str, str]:
    """Store private, best-effort redacted screenshot and DOM evidence for a failed run."""
    from packages.storage.objects import store_private_object

    await page.add_style_tag(content=(
        "input, textarea, select, [contenteditable='true'] "
        "{ color: transparent !important; text-shadow: none !important; }"
    ))
    screenshot = await page.screenshot(full_page=True, animations="disabled")
    html = await page.content()
    # Do not retain scripts or values from form controls in the DOM evidence.
    html = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "<script>[redacted]</script>", html)
    html = re.sub(r'(?is)\svalue=(["\']).*?\1', ' value="[redacted]"', html)
    html = re.sub(r"(?is)(<textarea\b[^>]*>).*?(</textarea>)", r"\1[redacted]\2", html)
    screenshot_obj = store_private_object(
        screenshot, "browser-failure.png", "image/png", owner_scope=owner_scope,
    )
    dom_obj = store_private_object(
        html.encode("utf-8"), "browser-failure.html", "text/html", owner_scope=owner_scope,
    )
    return {"screenshot_key": screenshot_obj["object_key"], "dom_key": dom_obj["object_key"]}
