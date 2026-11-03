import pytest
from packages.integrations.url_validation import validate_http_url

@pytest.mark.parametrize("value", ["https://example.com/jobs/1", "http://localhost:3000/role"])
def test_accepts_absolute_http_urls(value):
    assert validate_http_url(value) == value

@pytest.mark.parametrize("value", ["javascript:alert(1)", "file:///etc/passwd", "//example.com", "https://user:pass@example.com", "not-a-url"])
def test_rejects_unsafe_or_malformed_urls(value):
    with pytest.raises(ValueError):
        validate_http_url(value)

def test_empty_optional_url_is_allowed():
    assert validate_http_url("") == ""
