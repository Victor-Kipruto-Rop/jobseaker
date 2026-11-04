import pytest
from packages.automation.browser_adapter import action_digest, execute_approved_fill, assert_safe_target

class Locator:
    def __init__(self): self.value = ""
    async def count(self): return 1
    async def fill(self, value): self.value = value
    async def input_value(self): return self.value

class Page:
    url = "https://jobs.example/apply"
    def __init__(self): self.locator = Locator()
    def get_by_label(self, label, exact=True): return self.locator
    async def screenshot(self, full_page=False): return b"test-screenshot"

class Store:
    def __init__(self): self.done = {}
    def claim(self, action_id, payload_hash):
        if action_id in self.done: return False
        self.done[action_id] = None
        return True
    def complete(self, action_id, evidence): self.done[action_id] = evidence
    def fail(self, action_id, reason): self.done[action_id] = {"error": reason}

@pytest.mark.asyncio
async def test_adapter_requires_digest_and_records_evidence():
    digest = action_digest(1, "draft-hash", "email", "Email", "a@example.com")
    store = Store()
    result = await execute_approved_fill(Page(), application_id=1, draft_hash="draft-hash",
        field_id="email", label="Email", value="a@example.com",
        approved_digest=digest, approved_origin="https://jobs.example", evidence_owner_scope="1", action_store=store)
    assert result["status"] == "completed"
    assert result["evidence"]["verified"] is True
    assert result["evidence"]["screenshot_sha256"]

@pytest.mark.asyncio
async def test_adapter_rejects_modified_value_after_approval():
    digest = action_digest(1, "draft-hash", "email", "Email", "old@example.com")
    with pytest.raises(PermissionError):
        await execute_approved_fill(Page(), application_id=1, draft_hash="draft-hash",
            field_id="email", label="Email", value="new@example.com",
            approved_digest=digest, approved_origin="https://jobs.example", evidence_owner_scope="1", action_store=Store())

def test_adapter_rejects_origin_change():
    with pytest.raises(PermissionError):
        assert_safe_target("https://evil.example/apply", "https://jobs.example")
