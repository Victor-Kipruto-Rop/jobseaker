from apps.api.app.core.origin import is_allowed_origin, origin_from_referer

def test_accepts_exact_configured_origin():
    assert is_allowed_origin("https://app.example.com", ["https://app.example.com"])

def test_rejects_unlisted_host_and_scheme_downgrade():
    allowed = ["https://app.example.com"]
    assert not is_allowed_origin("https://evil.example.com", allowed)
    assert not is_allowed_origin("http://app.example.com", allowed)

def test_rejects_null_opaque_and_path_confused_origins():
    allowed = ["https://app.example.com"]
    assert not is_allowed_origin("null", allowed)
    assert not is_allowed_origin("https://app.example.com.attacker.test", allowed)
    assert not is_allowed_origin("https://app.example.com/path", allowed)

def test_referer_is_reduced_to_origin_and_malformed_values_fail_closed():
    assert origin_from_referer("https://app.example.com/a/b?x=1") == "https://app.example.com"
    assert origin_from_referer("javascript:alert(1)") == ""
    assert origin_from_referer("https://[") == ""

def test_normalizes_case_but_does_not_accept_unconfigured_ports():
    assert is_allowed_origin("HTTPS://APP.EXAMPLE.COM", ["https://app.example.com"])
    assert not is_allowed_origin("https://app.example.com:8443", ["https://app.example.com"])
