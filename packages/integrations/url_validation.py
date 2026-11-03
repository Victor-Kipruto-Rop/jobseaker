from urllib.parse import urlsplit

def validate_http_url(value: str, *, allow_empty: bool = True) -> str:
    value = value.strip()
    if not value and allow_empty:
        return value
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL must be an absolute HTTP or HTTPS URL without embedded credentials")
    return value
