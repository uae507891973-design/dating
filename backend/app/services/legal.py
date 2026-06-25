"""Каталог юридических документов и согласий (152-ФЗ).

Источник правды по версиям и обязательности документов, которые пользователь
принимает при регистрации. Версии берутся из настроек, чтобы при обновлении
текста документа можно было запросить повторное согласие.
"""

from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()


@dataclass(frozen=True)
class LegalDoc:
    type: str
    version: str
    title: str
    url: str
    required: bool


def documents() -> list[LegalDoc]:
    return [
        LegalDoc(
            type="privacy",
            version=settings.consent_privacy_version,
            title="Согласие на обработку персональных данных",
            url="/legal/privacy",
            required=True,
        ),
        LegalDoc(
            type="terms",
            version=settings.consent_terms_version,
            title="Пользовательское соглашение и оферта",
            url="/legal/terms",
            required=True,
        ),
        LegalDoc(
            type="marketing",
            version=settings.consent_marketing_version,
            title="Согласие на информационные рассылки",
            url="/legal/marketing",
            required=False,
        ),
    ]


def required_types() -> set[str]:
    return {d.type for d in documents() if d.required}


def version_for(doc_type: str) -> str | None:
    for d in documents():
        if d.type == doc_type:
            return d.version
    return None
