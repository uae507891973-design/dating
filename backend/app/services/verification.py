"""Селфи-верификация (liveness + сверка) — заглушка.

На фундаменте проверка детерминирована (по содержимому/имени), чтобы
отрабатывать ветки approved/rejected. Реальная проверка liveness и сверка с
фото профиля подключаются через check_selfie без изменения логики.
"""


def check_selfie(content: bytes, filename: str = "") -> bool:
    """True — верификация пройдена (живой человек, лицо совпало)."""
    if not content:
        return False
    haystack = (filename or "").lower()
    marker = content[:64].lower()
    if "fail" in haystack or b"fail" in marker:
        return False
    return True
