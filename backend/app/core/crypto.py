"""Шифрование ПДн в покое (152-ФЗ).

Используется детерминированное шифрование AES-SIV: одинаковый открытый текст даёт
одинаковый шифртекст, поэтому поле можно шифровать прозрачно и при этом искать по
равенству (`WHERE phone == ...`) и держать unique-индекс. Ключ выводится из
`pii_secret` — в prod он обязателен (см. validate_prod_settings).
"""

import base64
import hashlib

from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from sqlalchemy import String, TypeDecorator

from app.core.config import get_settings

settings = get_settings()


def _cipher() -> AESSIV:
    # 64-байтный ключ AES-SIV из секрета.
    key = hashlib.sha512(settings.pii_secret.encode()).digest()
    return AESSIV(key)


def encrypt_str(value: str) -> str:
    token = _cipher().encrypt(value.encode(), None)
    return base64.urlsafe_b64encode(token).decode()


def decrypt_str(value: str) -> str:
    token = base64.urlsafe_b64decode(value.encode())
    return _cipher().decrypt(token, None).decode()


class EncryptedStr(TypeDecorator):
    """String-поле, прозрачно шифруемое в покое (детерминированно)."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt_str(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        try:
            return decrypt_str(value)
        except Exception:  # noqa: BLE001 — не падать на «сырых» значениях
            return value
