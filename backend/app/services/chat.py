"""Чат: real-time соединения, модерация сообщений и айсбрейкеры."""

import re
import uuid
from collections import defaultdict

from fastapi import WebSocket

from app.services.compatibility import CATEGORY_LABELS

# Паттерны контактов/ссылок — для антиспама в первых сообщениях.
_URL_RE = re.compile(r"https?://|www\.|t\.me/|@\w+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?\d[\s\-()]?){7,}")


def screen_message(body: str, sender_verified: bool) -> tuple[bool, str | None]:
    """Базовая модерация сообщения. Возвращает (можно_отправить, причина)."""
    text = body.strip()
    if not text:
        return False, "empty message"
    if len(text) > 4000:
        return False, "message too long"
    # Неверифицированным запрещаем ссылки/контакты (антискам).
    if not sender_verified and (_URL_RE.search(text) or _PHONE_RE.search(text)):
        return False, "links and contacts are not allowed before verification"
    return True, None


def generate_icebreakers(
    category_contributions: dict[str, float],
    display_name: str | None = None,
) -> list[str]:
    """Подсказки для первого сообщения на основе сильных совпадений."""
    name = display_name or "вы"
    strong = sorted(
        ((c, v) for c, v in category_contributions.items() if v >= 0.7),
        key=lambda x: x[1],
        reverse=True,
    )
    suggestions: list[str] = []
    templates = {
        "values": "У вас близкие ценности — спросите, что для {name} важно.",
        "goals": "Вы оба нацелены на серьёзное — обсудите, каким видите будущее.",
        "lifestyle": "Похожий образ жизни — спросите про идеальные выходные.",
        "family": "Близкие взгляды на семью — мягко затроньте эту тему.",
        "communication": "Схожий стиль общения — спросите про любимые вечера.",
    }
    for cat, _ in strong[:2]:
        tpl = templates.get(cat)
        if tpl:
            suggestions.append(tpl.format(name=name))

    # Дополняем нейтральными вариантами.
    suggestions.append("Что в анкете зацепило вас больше всего?")
    if not suggestions:
        suggestions.append("Расскажите, как прошёл ваш день?")
    return suggestions[:3]


def label_for(category: str) -> str:
    return CATEGORY_LABELS.get(category, category)


class ConnectionManager:
    """In-memory реестр WebSocket-соединений по чатам (мэтчам)."""

    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, match_id: uuid.UUID, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms[match_id].add(ws)

    def disconnect(self, match_id: uuid.UUID, ws: WebSocket) -> None:
        self._rooms[match_id].discard(ws)
        if not self._rooms[match_id]:
            self._rooms.pop(match_id, None)

    def connections(self, match_id: uuid.UUID) -> set[WebSocket]:
        return set(self._rooms.get(match_id, set()))

    async def broadcast(self, match_id: uuid.UUID, payload: dict) -> None:
        for ws in self.connections(match_id):
            await ws.send_json(payload)


manager = ConnectionManager()
