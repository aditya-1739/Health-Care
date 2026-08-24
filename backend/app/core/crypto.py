import base64
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.core.config import settings


def _get_fernet() -> Fernet:
    """Derive a valid 32-byte url-safe base64-encoded key from settings."""
    raw_key = settings.OAUTH_ENCRYPTION_KEY.encode("utf-8")
    try:
        # If it's already a valid 32-byte Fernet key
        return Fernet(raw_key)
    except Exception:
        # Derive key using PBKDF2HMAC with static salt for deterministic decryption
        salt = b"healthcare_oauth_static_salt_v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(raw_key))
        return Fernet(derived_key)


def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    """Encrypt a sensitive token (e.g. access_token, refresh_token) before database storage."""
    if not plain_token:
        return None
    f = _get_fernet()
    encrypted_bytes = f.encrypt(plain_token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt an encrypted token in-memory only when required by the calendar service."""
    if not encrypted_token:
        return None
    f = _get_fernet()
    try:
        decrypted_bytes = f.decrypt(encrypted_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception:
        # Return None if decryption fails (e.g. key changed or invalid format)
        return None
