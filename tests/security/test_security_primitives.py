import pytest
from apps.api.app.core.security import hash_password, verify_password

def test_password_hash_is_not_plaintext():
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)

def test_short_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password("short")
