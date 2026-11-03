from urllib.parse import urlsplit

def is_allowed_origin(candidate: str | None, allowed_origins: list[str]) -> bool:
    """Compare a browser Origin/Referer origin against explicit configured origins."""
    if not candidate or candidate == "null":
        return False
    try:
        parsed = urlsplit(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            return False
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            return False
        normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
        configured = set()
        for value in allowed_origins:
            item = urlsplit(value.strip())
            if item.scheme in {"http", "https"} and item.netloc and not item.path and not item.query and not item.fragment:
                configured.add(f"{item.scheme.lower()}://{item.netloc.lower()}")
        return normalized in configured
    except ValueError:
        return False

def origin_from_referer(referer: str | None) -> str | None:
    """Extract only the origin from a full Referer URL; malformed values fail closed."""
    if not referer:
        return None
    try:
        parsed = urlsplit(referer)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            return ""
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    except ValueError:
        return ""
