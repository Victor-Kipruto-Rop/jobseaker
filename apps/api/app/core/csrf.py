"""CSRF token checks shared by the HTTP boundary and regression tests."""
import hashlib
import hmac


def double_submit_matches(cookie_token: str | None, header_token: str | None) -> bool:
    """Require a non-empty CSRF cookie and matching request header."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def token_is_bound_to_session(cookie_token: str | None, session_csrf_hash: str | None) -> bool:
    """Verify that the presented CSRF token is the one bound to this session."""
    if not cookie_token or not session_csrf_hash:
        return False
    digest = hashlib.sha256(cookie_token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, session_csrf_hash)
