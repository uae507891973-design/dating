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

## Что сделано на Стадии 1.2 (онбординг и тест совместимости)
- Каталог теста совместимости (16 вопросов, 5 категорий: ценности, цели, образ жизни, семья, общение) — `GET /v1/onboarding/questions`.
- Приём ответов с важностью, идемпотентное перепрохождение — `POST /v1/onboarding/answers`.
- Расчёт **психопрофиля** (вектор по категориям) и фиксация **намерения** (брак/отношения/дружба); активация пользователя.
- Статус онбординга — `GET /v1/onboarding/status`.
- **Функция совместимости** (`services/compatibility.py`) — взвешенный по важности скоринг 0..100 + вклад категорий (сырьё для объяснимого мэтчинга, Стадия 2).
- Событие аналитики `test_completed`.

## Что сделано на Стадии 1.3 (анкета и модерация контента)
- CRUD анкеты: `GET/PUT /v1/profile` с проверкой возраста **18+**.
- Загрузка фото `POST /v1/profile/photos` (multipart), список и удаление; лимит фото и размера.
- **Авто-модерация (NSFW)**: классификатор-заглушка + пороги → `approved` / `pending` (ручная проверка) / `rejected`.
- Хранилище медиа (локальное, интерфейс под объектное хранилище РФ).
- **Модераторская очередь** (RBAC: moderator/admin): `GET /v1/moderation/photos`, `POST /v1/moderation/photos/{id}/decision`.
- События аналитики: `profile_completed`, `photo_uploaded`, `photo_moderated`.

## Что сделано на Стадии 1.4 (верификация, безопасность) — MVP-ядро закрыто
- **Селфи-верификация** `POST /v1/verify/selfie` (liveness/сверка — заглушка) + бейдж `is_verified` в анкете; `GET /v1/verify/status`.
- **Жалобы** `POST /v1/reports` и **блокировки** `POST/GET/DELETE /v1/blocks` (идемпотентно, нельзя на себя).
- **Аудит-лог** доступа/действий (152-ФЗ): запись на верификацию, жалобу, блок, модерационное решение; чтение `GET /v1/moderation/audit` (RBAC).
- События аналитики: `verification_completed`, `report_created`, `user_blocked`.

> Реальные liveness/сверка лица, шифрование PII и полноценный SIEM для аудита — следующие итерации; интерфейсы заложены.

## Что сделано на Стадии 2.1 (движок подбора)
- Кандидатогенерация по фильтрам: активные пользователи, взаимная ориентация по полу, исключение себя/заблокированных/уже оценённых.
- **Ранжирование по совместимости** (взвешенный скоринг из теста) — `GET /v1/discovery`.
- Лайк/пропуск (`POST /v1/discovery/like`, `/skip`); при взаимном лайке создаётся **мэтч**.
- Модели `likes`/`matches` + миграция 0005; события `like`, `match_created`.

> Гео-фильтр (PostGIS-радиус) и кэш кандидатов в Redis — оптимизации, отложены.

## Что сделано на Стадии 2.2 (объяснимый мэтчинг — ключевой дифференциатор)
- **«Почему вы подходите»**: честные причины из реальных факторов скоринга
  (вклад сильных категорий + совпадение намерений) — поле `reasons` в подборке.
- **Scrutability**: важность категорий (`muted`/`normal`/`important`) влияет на
  ранжирование — `GET/PUT /v1/discovery/preferences`.
- Модель `category_preferences` + миграция 0006; событие `preferences_updated`.

## Что сделано на Стадии 2.3 (чат) — Стадия 2 завершена
- Список мэтчей `GET /v1/matches`; история `GET /v1/matches/{id}/messages`.
- Отправка `POST /v1/matches/{id}/messages` с модерацией (антиспам: ссылки/контакты
  блокируются для неверифицированных), отметка прочтения `POST .../read`.
- **Айсбрейкеры** `GET /v1/matches/{id}/icebreakers` на основе сильных совпадений.
- **Real-time** через WebSocket `/v1/ws/chat/{match_id}` (авторизация по токену,
  проверка членства, broadcast подключённым).
- Доступ только участникам мэтча; модель `messages` + миграция 0007.
- События `message_sent`.

> PostGIS-геометрия запланирована: на фундаменте координаты хранятся как `latitude/longitude` (Float), миграция на `geography(Point)` — в рамках Стадии 2 (подбор по гео).
