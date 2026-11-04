"""Versioned AES-256-GCM credential envelope with explicit key rotation.

Set JOBSEEKER_CREDENTIAL_KEYRING to a JSON object mapping key IDs to
URL-safe-base64 32-byte keys, and JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID to the
key ID used for new writes. Keep old keys in the keyring until every stored
credential has been rewrapped. JOBSEEKER_CREDENTIAL_KEK remains supported as
the legacy single-key source for existing v1 ciphertext.
"""
from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_ENV = "JOBSEEKER_CREDENTIAL_KEK"
KEYRING_ENV = "JOBSEEKER_CREDENTIAL_KEYRING"
ACTIVE_KEY_ENV = "JOBSEEKER_CREDENTIAL_ACTIVE_KEY_ID"
AAD_PREFIX = b"jobseeker:credential:"


def _decode_key(raw: str, key_id: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise RuntimeError(f"Credential key {key_id!r} must be URL-safe base64") from exc
    if len(key) != 32:
        raise RuntimeError(f"Credential key {key_id!r} must decode to exactly 32 bytes")
    return key


def _keyring() -> tuple[dict[str, bytes], str]:
    settings = None
    try:
        from apps.api.app.core.config import get_settings
        settings = get_settings()
    except Exception:
        pass
    raw_ring = os.getenv(KEYRING_ENV, "") or (settings.credential_keyring if settings else "") or ""
    keys: dict[str, bytes] = {}
    if raw_ring:
        try:
            values = json.loads(raw_ring)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{KEYRING_ENV} must be a JSON object") from exc
        if not isinstance(values, dict) or not values:
            raise RuntimeError(f"{KEYRING_ENV} must contain at least one key")
        for key_id, raw in values.items():
            if (not isinstance(key_id, str) or not key_id or len(key_id) > 64
                    or not isinstance(raw, str)):
                raise RuntimeError("Credential keyring entries must map short IDs to base64 strings")
            keys[key_id] = _decode_key(raw, key_id)

    legacy = os.getenv(KEY_ENV, "")
    if not legacy:
        try:
            from apps.api.app.core.config import get_settings
            legacy = get_settings().credential_kek or ""
        except Exception:
            legacy = ""
    if legacy:
        keys.setdefault("legacy", _decode_key(legacy, "legacy"))

    if not keys:
        raise RuntimeError(f"{KEYRING_ENV} or {KEY_ENV} is required to encrypt credentials")
    active = os.getenv(ACTIVE_KEY_ENV, "") or (
        settings.credential_active_key_id if settings else ""
    ) or ""
    if not active:
        active = next((key_id for key_id in keys if key_id != "legacy"), "legacy")
    if active not in keys:
        raise RuntimeError(f"Active credential key ID {active!r} is missing from the keyring")
    return keys, active


def encrypt_credential(plaintext: str, *, purpose: str) -> str:
    if not purpose or len(purpose) > 80:
        raise ValueError("purpose must contain 1..80 characters")
    keys, active_id = _keyring()
    nonce = os.urandom(12)
    aad = AAD_PREFIX + b"v2:" + active_id.encode("utf-8") + b":" + purpose.encode("utf-8")
    cipher = AESGCM(keys[active_id]).encrypt(nonce, plaintext.encode("utf-8"), aad)
    payload = base64.urlsafe_b64encode(nonce + cipher).decode("ascii")
    return f"v2:{active_id}:{payload}"


def decrypt_credential(token: str, *, purpose: str) -> str:
    if not purpose or len(purpose) > 80:
        raise ValueError("purpose must contain 1..80 characters")
    keys, _ = _keyring()
    if token.startswith("v1:"):
        key = keys.get("legacy")
        if key is None:
            raise RuntimeError("Legacy credential key is not available for v1 ciphertext")
        raw = base64.urlsafe_b64decode(token[3:])
        aad = AAD_PREFIX + b"v1:" + purpose.encode("utf-8")
    elif token.startswith("v2:"):
        try:
            _, key_id, encoded = token.split(":", 2)
        except ValueError as exc:
            raise ValueError("Malformed v2 credential envelope") from exc
        key = keys.get(key_id)
        if key is None:
            raise RuntimeError(f"Credential decryption key {key_id!r} is not available")
        raw = base64.urlsafe_b64decode(encoded)
        aad = AAD_PREFIX + b"v2:" + key_id.encode("utf-8") + b":" + purpose.encode("utf-8")
    else:
        raise ValueError("Unsupported credential ciphertext version")
    if len(raw) < 29:
        raise ValueError("Credential ciphertext is truncated")
    plain = AESGCM(key).decrypt(raw[:12], raw[12:], aad)
    return plain.decode("utf-8")


def rewrap_credential(token: str, *, purpose: str) -> str:
    """Re-encrypt a credential with the currently active key without changing its value."""
    plaintext = decrypt_credential(token, purpose=purpose)
    return encrypt_credential(plaintext, purpose=purpose)


def credential_key_id(token: str) -> str:
    """Return the non-secret key identifier for rotation inventory."""
    if token.startswith("v1:"):
        return "legacy"
    if token.startswith("v2:"):
        parts = token.split(":", 2)
        if len(parts) == 3 and parts[1]:
            return parts[1]
    raise ValueError("Unsupported or malformed credential ciphertext")


def credential_needs_rotation(token: str) -> bool:
    """Return whether a versioned ciphertext should be rewrapped with the active key."""
    _, active_id = _keyring()
    return credential_key_id(token) != active_id
