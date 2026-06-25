"""Схемы аутентификации (OTP + JWT)."""

import re

from pydantic import BaseModel, field_validator

PHONE_RE = re.compile(r"^\+?[1-9]\d{9,14}$")


class RequestOtpIn(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not PHONE_RE.match(v):
            raise ValueError("invalid phone format")
        return v


class RequestOtpOut(BaseModel):
    sent: bool
    retry_after_sec: int


class VerifyOtpIn(BaseModel):
    phone: str
    code: str
    # Типы принятых документов (галочки согласий): privacy, terms, marketing.
    accepted_documents: list[str] = []


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False


class RefreshIn(BaseModel):
    refresh_token: str
