# epic-davinci — backend

Backend сервиса знакомств (Стадия 0 — технический фундамент).

Стек: **FastAPI**, **SQLAlchemy 2.0 (async)**, **Alembic**, **PostgreSQL** (PostGIS — план), **Redis**.

## Локальный запуск

```bash
# 1. Поднять зависимости (Postgres + Redis) и API
docker compose up --build

# API: http://localhost:8000
# Healthcheck: http://localhost:8000/health
# OpenAPI/Swagger: http://localhost:8000/docs
```

### Запуск без Docker (для разработки)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # отредактировать при необходимости
alembic upgrade head            # применить миграции
uvicorn app.main:app --reload
```

## Тесты и линт

```bash
cd backend
pip install -r requirements-dev.txt
ruff check app tests            # линт
pytest                          # тесты
```

## Структура

```
app/
  main.py            # точка входа, сборка приложения
  core/config.py     # конфигурация (pydantic-settings)
  core/logging.py    # структурное логирование
  db/                # сессии и базовый класс моделей
  models/            # ORM-модели (users, profiles, consents)
  schemas/           # Pydantic-схемы
  api/v1/            # роуты v1 (health)
  services/          # сервисы (analytics)
migrations/          # Alembic
tests/               # pytest
```

## Что сделано на Стадии 0
- Каркас приложения, конфиг, структурное логирование.
- Слой БД (async SQLAlchemy) + Alembic-миграция с базовыми сущностями.
- Healthcheck и автогенерируемая OpenAPI.
- Сервис аналитики (событийное логирование) + событие `app_started`.
- Docker/Compose, CI (lint + tests).

## Что сделано на Стадии 1.1 (регистрация и аккаунт)
- Регистрация/вход по **SMS-OTP** (`POST /v1/auth/request-otp`, `/v1/auth/verify-otp`):
  - генерация кода, хранение с TTL (Redis в проде, in-memory для тестов);
  - лимиты: запросов кода на телефон и попыток ввода;
  - SMS-отправка — заглушка (код в лог), интерфейс под РФ-провайдера.
- **JWT** access/refresh + обновление (`POST /v1/auth/refresh`).
- Создание пользователя при первом успешном входе (`is_new_user`).
- **Согласия 152-ФЗ** (`POST/GET /v1/consents`) с версией документа и таймстампом, под авторизацией.
- События аналитики: `otp_requested`, `registration_completed`, `login`, `consent_accepted`.

> SMS-провайдер, шифрование PII и сами тексты документов согласий подключаются далее; интерфейсы под это уже заложены.

> PostGIS-геометрия запланирована: на фундаменте координаты хранятся как `latitude/longitude` (Float), миграция на `geography(Point)` — в рамках Стадии 2 (подбор по гео).
