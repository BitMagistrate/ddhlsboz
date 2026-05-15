# ЧитАИ — ИИ-куратор русской культурно-образовательной среды

[![CI](https://github.com/BitMagistrate/ddhlsboz/actions/workflows/ci.yml/badge.svg)](https://github.com/BitMagistrate/ddhlsboz/actions/workflows/ci.yml)
![Backend tests](https://img.shields.io/badge/backend_tests-224%2B-green)
![Frontend tests](https://img.shields.io/badge/frontend_tests-41%2B-green)
![Bots-core tests](https://img.shields.io/badge/bots--core_tests-14-green)
![RAG MRR](https://img.shields.io/badge/RAG_MRR-0.979-blue)
![Recall@5](https://img.shields.io/badge/Recall%405-0.985-blue)

> **Книги, игры и наставник — в одном приложении.** Чтение русской классики (Пушкин/Лермонтов/Гоголь/Толстой/Достоевский) с гарантированными цитатами, конспекты из ваших документов и обучающие игры. Для аудитории 14–22 (школьники и студенты). Совместимо с Пушкинской картой.

## Mode

1. **«Литература»** — AI-куратор: маршрут чтения на 4 недели по произведению из public-domain корпуса РГБ, цитаты с указанием страницы/главы, mind-map, SRS-карточки, TTS озвучка, экспорт в Markdown / iCalendar.
2. **«Учёба»** — загрузка PDF / аудио / видео / URL → конспект, summary, flashcards, quiz, mind-map. _(Upload pipeline в работе — см. `docs/ROADMAP.md` §EX1–EX5.)_
3. **«Игра»** — Brain Dash (3D endless runner с блиц-вопросами по тексту произведения). Вопросы из конспекта пользователя.

## Стек (полностью российский, ready for B2G)

- LLM: **GigaChat MAX** (Sber) → **YandexGPT 5 Pro** → deterministic mock fallback
- TTS: **Yandex SpeechKit**
- RAG: BM25 + dense embeddings + RRF reranker
- 152-ФЗ: consent / export / forget / audit-log
- Telegram-бот (aiogram 3) + multi-channel core (VK, MAX, Web, Alice)
- PWA + WCAG 2.1 AA
- CI: ruff + mypy + pytest + bandit + coverage 70% + RAG-benchmark gate + gitleaks

## Документация

- [docs/ROADMAP.md](docs/ROADMAP.md) — главный план (единый источник правды)
- [docs/PRODUCT.md](docs/PRODUCT.md) — описание продукта, бизнес-модель, юнит-экономика
- [docs/STATE.md](docs/STATE.md) — текущее состояние кодовой базы
- [docs/STRATEGY.md](docs/STRATEGY.md) — стратегия победы в конкурсах
- [docs/PROMPTS.md](docs/PROMPTS.md) — банк промптов для AI-ассистентов
- [docs/DEV_KIT.md](docs/DEV_KIT.md) — справочник для разработчиков
- [docs/STUDY_MODE_SPEC.md](docs/STUDY_MODE_SPEC.md) — спецификация mode «Учёба» (DRAFT)
- [docs/GAMES_SPEC.md](docs/GAMES_SPEC.md) — спецификация игры Brain Dash
- [docs/pitch/pitch.md](docs/pitch/pitch.md) — питч-дек (Marp)
- [evaluation/README.md](evaluation/README.md) — открытый RAG-бенчмарк (reproducible)
- [AGENTS.md](AGENTS.md) — инструкции для AI-ассистентов

## Запуск локально

```bash
# Backend
cd backend && poetry install && poetry run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Telegram bot (опционально, нужны секреты в окружении)
cd bot && pip install -r requirements.txt && python bot.py

# Multi-channel bots (VK, MAX)
cd bots && pip install -e . && python -m bots.adapters.vk    # или max
```

## Конкурсы

- 🏆 **Нейрофест 2026** — акселератор стартапов с ИИ
- 📚 **Книга будущего 2026**
- 🇷🇺 **Моя страна — моя Россия 2026** (президентский конкурс)

См. [docs/STRATEGY.md](docs/STRATEGY.md) для подробностей.

## Лицензия

Код: MIT (см. `LICENSE`). Корпус: только public-domain произведения (авторы умерли > 70 лет назад, ст. 1281 ГК РФ).
