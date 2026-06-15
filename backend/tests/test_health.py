"""Тесты healthcheck и корневого эндпоинта."""

from httpx import AsyncClient


async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "epic-davinci"


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "epic-davinci"
    assert "version" in body
