# epic-davinci — платформа серьёзных онлайн-знакомств

Продукт в нише серьёзных знакомств в России: **без пошлостей**, с фокусом на **доверие и совместимость**.

## Документация

- [Исследование рынка (РФ, 2025)](docs/research/dating-market-ru.md)
- [Исследование функций: объяснимый мэтчинг и видеознакомство «вслепую»](docs/research/feature-research-matching-video.md)
- [Анализ функционала конкурентов](docs/product/competitor-analysis.md)
- [Дорожная карта](docs/product/roadmap.md)
- [Поэтапный план разработки](docs/product/development-plan.md)
- [Подробные этапы реализации](docs/product/implementation-stages.md)
- Детальное описание стадий:
  - [Стадия 0 — Подготовка и фундамент](docs/product/stages/stage-0-foundation.md)
  - [Стадия 1 — MVP-ядро](docs/product/stages/stage-1-mvp-core.md)
  - [Стадия 2 — Мэтчинг и общение](docs/product/stages/stage-2-matching-chat.md)
  - [Стадия 3 — Доверие, видео, антифрод](docs/product/stages/stage-3-trust-video.md)
  - [Стадия 4 — Монетизация](docs/product/stages/stage-4-monetization.md)
  - [Стадия 5 — Рост и масштаб](docs/product/stages/stage-5-growth-scale.md)

## Код

- [`backend/`](backend/) — API-сервис (FastAPI). Запуск: `docker compose up --build`, далее http://localhost:8000/docs
- Стадия 0 (фундамент) реализована: каркас приложения, слой БД + миграции, healthcheck, аналитика, Docker/Compose, CI.
- [Customer Journey Map](docs/product/cjm.md)
- [План реализации продукта (+ оригинальные идеи)](docs/product/implementation-plan.md)

## Кратко

- **Рынок:** ~8–10 млрд ₽, ~8 млн MAU; лидеры Mamba (39%) и VK Знакомства (29%).
- **Тренд 2025:** осознанный поиск долгосрочных отношений, AI-совместимость, борьба с ботами.
- **Наше право на существование:** объяснимый мэтчинг по ценностям, verified-by-default, slow dating, безопасность как фича.
