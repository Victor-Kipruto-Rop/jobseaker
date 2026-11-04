"""Authenticated envelope encryption for third-party credentials.

JOBSEEKER_CREDENTIAL_KEK must be a base64-encoded 32-byte key supplied by a
secret manager. Production must rotate this key and rewrap stored data using
key_version metadata. The application secret is deliberately not reused.
"""
from __future__ import annotations
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_ENV = "JOBSEEKER_CREDENTIAL_KEK"
AAD_PREFIX = b"jobseeker:credential:v1:"


def _key() -> bytes:
    raw = os.getenv(KEY_ENV, "")
    if not raw:
        raise RuntimeError(f"{KEY_ENV} is required to encrypt credentials")
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise RuntimeError(f"{KEY_ENV} must be URL-safe base64") from exc
    if len(key) != 32:
        raise RuntimeError(f"{KEY_ENV} must decode to exactly 32 bytes")
    return key


def encrypt_credential(plaintext: str, *, purpose: str) -> str:
    if not purpose or len(purpose) > 80:
        raise ValueError("purpose must contain 1..80 characters")
    nonce = os.urandom(12)
    cipher = AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), AAD_PREFIX + purpose.encode())
    return "v1:" + base64.urlsafe_b64encode(nonce + cipher).decode("ascii")


def decrypt_credential(token: str, *, purpose: str) -> str:
    if not token.startswith("v1:"):
        raise ValueError("Unsupported credential ciphertext version")
    raw = base64.urlsafe_b64decode(token[3:])
    if len(raw) < 29:
        raise ValueError("Credential ciphertext is truncated")
    plain = AESGCM(_key()).decrypt(raw[:12], raw[12:], AAD_PREFIX + purpose.encode())
    return plain.decode("utf-8")
