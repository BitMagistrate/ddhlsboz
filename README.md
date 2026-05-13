# ЧитАИ — учебный прототип ИИ-помощника по русской литературе

> Личный проект. **Ранняя альфа, не задеплоено.** Готов показать как работает локально.

## Статус проекта

Это **прототип**. На сегодня:

- ✅ Код есть на GitHub, открыт под MIT.
- ✅ Серверная часть (FastAPI + RAG) запускается локально, проходит около 270 unit-тестов.
- ✅ Веб-интерфейс (React + TypeScript) собирается и запускается локально.
- ✅ Игра Brain Dash (3D-runner на three.js) работает в браузере.
- ✅ Telegram-бот написан (aiogram 3), но публично не запущен.
- ❌ **Сайт в интернете не задеплоен.** Домена нет.
- ❌ **Бот публично не запущен.** Токена в проде нет.
- ❌ **Реальных пользователей нет.** Метрики поиска (MRR, Recall) — на синтетическом наборе из 48 запросов, не на живых юзерах.
- ❌ Реальных пилотов в школах / библиотеках нет.

## Идея

Помощник по русской литературе для подростков 14–22 лет, который **отвечает только цитатами из текста произведения**. ChatGPT и подобные модели часто галлюцинируют на классике — выдумывают цитаты, путают героев. Я попробовал сделать иначе: если данных нет, система честно отказывается отвечать, а не выдумывает.

Три режима:

1. **Литература** — куратор чтения: маршрут на 4 недели по произведению из public-domain корпуса, цитаты с указанием источника, SRS-карты для повторения, TTS озвучка.
2. **Учёба** — конспекты, summary, flashcards, quiz, ментальная карта (upload pipeline частично — см. `docs/ROADMAP.md`).
3. **Игра** — Brain Dash, 3D-runner на three.js, вопросы во время бега берутся из текста произведения.

## Стек

- Backend: FastAPI (Python 3.12) + Poetry, pydantic v2
- Frontend: React 18 + TypeScript + Vite + Tailwind
- LLM (опционально, нужны ключи): GigaChat MAX → YandexGPT 5 Pro → детерминистский mock fallback
- TTS (опционально): Yandex SpeechKit
- RAG: BM25 + dense embeddings + RRF reranker
- Bots: aiogram 3 (Telegram), multi-channel core с адаптерами для VK / MAX
- CI: ruff + mypy + pytest + bandit + coverage 70% + gitleaks

## Запуск локально

```bash
# Backend
cd backend && poetry install
poetry run uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs — Swagger

# Frontend
cd frontend && npm install
npm run dev
# → http://localhost:5173

# Telegram bot (нужен TELEGRAM_BOT_TOKEN в .env)
cd bot && pip install -r requirements.txt
python bot.py

# Тесты
cd backend && poetry run pytest -q
cd frontend && npm test -- --run
```

## Документация

- [docs/ROADMAP.md](docs/ROADMAP.md) — план развития (то, что планировал сделать)
- [docs/PRODUCT.md](docs/PRODUCT.md) — описание продукта
- [docs/STATE.md](docs/STATE.md) — что реально сделано
- [docs/STUDY_MODE_SPEC.md](docs/STUDY_MODE_SPEC.md) — спецификация mode «Учёба» (DRAFT)
- [docs/GAMES_SPEC.md](docs/GAMES_SPEC.md) — спецификация игры Brain Dash
- [docs/pitch/pitch.md](docs/pitch/pitch.md) — питч-дек (Marp)
- [evaluation/README.md](evaluation/README.md) — RAG-бенчмарк (синтетический, 48 запросов)
- [AGENTS.md](AGENTS.md) — инструкции для AI-ассистентов

## Контакты

- Автор: Ермоленко Владимир, Красноярск
- Город: Красноярск
- Email: scaleblinkk@vk.com
- Telegram: связь через email
- GitHub: [BitMagistrate](https://github.com/BitMagistrate)

## Лицензия

Код: MIT (см. `LICENSE`). Корпус: только public-domain произведения (авторы умерли > 70 лет назад, ст. 1281 ГК РФ).
