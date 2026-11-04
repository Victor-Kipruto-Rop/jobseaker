import asyncio

from packages.automation import form_assist


class FakePage:
    def __init__(self):
        self.styles = []
        self.html = (
            '<html><script>private script secret</script>'
            '<input name="email" value="victor@example.com">'
            '<textarea>private cover letter text</textarea></html>'
        )

    async def add_style_tag(self, *, content):
        self.styles.append(content)

    async def screenshot(self, **kwargs):
        return b"image-bytes"

    async def content(self):
        return self.html


def test_browser_failure_evidence_redacts_dom_and_keeps_objects_private(monkeypatch):
    stored = {}

    def fake_store(data, filename, content_type, *, owner_scope):
        key = f"{owner_scope}/{filename}"
        stored[key] = data
        return {"object_key": key}

    monkeypatch.setattr("packages.storage.objects.store_private_object", fake_store)
    page = FakePage()
    result = asyncio.run(form_assist.capture_failure_evidence(page, owner_scope="candidate-42"))
    dom = stored[result["dom_key"]].decode()
    assert "private script secret" not in dom
    assert "victor@example.com" not in dom
    assert "private cover letter text" not in dom
    assert "[redacted]" in dom
    assert result["screenshot_key"].startswith("candidate-42/")
    assert result["dom_key"].startswith("candidate-42/")
