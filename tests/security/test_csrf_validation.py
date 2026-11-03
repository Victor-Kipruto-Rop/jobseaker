from apps.api.app.core.csrf import double_submit_matches, token_is_bound_to_session
import hashlib


def test_double_submit_rejects_missing_or_mismatched_values():
    assert double_submit_matches("abc", "abc")
    assert not double_submit_matches("abc", "def")
    assert not double_submit_matches(None, "abc")
    assert not double_submit_matches("abc", None)
    assert not double_submit_matches("", "")


def test_csrf_token_must_match_session_digest():
    token = "csrf-token-value"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token_is_bound_to_session(token, digest)
    assert not token_is_bound_to_session(token + "x", digest)
    assert not token_is_bound_to_session(None, digest)
