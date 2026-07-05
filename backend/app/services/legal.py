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


# Тексты документов (заглушки; финальные редакции — от юриста).
DOCUMENT_TEXTS: dict[str, str] = {
    "privacy": (
        "Согласие на обработку персональных данных\n\n"
        "Регистрируясь в сервисе, вы даёте согласие на обработку ваших "
        "персональных данных (номер телефона, данные анкеты, фотографии) в "
        "соответствии с Федеральным законом №152-ФЗ «О персональных данных». "
        "Данные хранятся на территории РФ, используются для работы сервиса "
        "знакомств и не передаются третьим лицам без вашего согласия. Вы вправе "
        "отозвать согласие и удалить аккаунт в любой момент."
    ),
    "terms": (
        "Пользовательское соглашение и оферта\n\n"
        "Сервис предоставляется на условиях настоящей оферты. Пользователь "
        "обязуется быть старше 18 лет, указывать достоверные данные, соблюдать "
        "правила общения без оскорблений и запрещённого контента. Администрация "
        "вправе модерировать контент и блокировать нарушителей. Платные функции "
        "предоставляются на условиях подписки/разовых покупок."
    ),
    "marketing": (
        "Согласие на информационные рассылки\n\n"
        "Вы соглашаетесь получать информационные и рекламные сообщения о "
        "сервисе. Согласие добровольное, его можно отозвать в настройках."
    ),
}


def document_text(doc_type: str) -> str | None:
    return DOCUMENT_TEXTS.get(doc_type)


def required_types() -> set[str]:
    return {d.type for d in documents() if d.required}


def version_for(doc_type: str) -> str | None:
    for d in documents():
        if d.type == doc_type:
            return d.version
    return None


async def missing_reconsents(db, user_id) -> list[str]:
    """Обязательные документы, по которым нет согласия на актуальную версию.

    Если версия документа выросла, старое согласие не считается — требуется
    переподтверждение (152-ФЗ).
    """
    from sqlalchemy import select

    from app.models import Consent

    accepted = set(
        (
            await db.execute(
                select(Consent.doc_type, Consent.doc_version).where(
                    Consent.user_id == user_id
                )
            )
        ).all()
    )
    missing = []
    for d in documents():
        if d.required and (d.type, d.version) not in accepted:
            missing.append(d.type)
    return sorted(missing)
