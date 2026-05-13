# AGENTS.md

> Инструкции для AI-ассистентов (Devin, Cursor, Codex), работающих в этом репо.
> Перед любым изменением — прочитать целиком.

## Стек

- Python 3.12 + Poetry, FastAPI, pydantic v2 (backend)
- React 18 + TypeScript + Vite + Tailwind + vitest (frontend)
- aiogram 3 (Telegram bot — оставлен рабочим)
- `bots/` — multi-channel core (VK / MAX / Web / Alice) поверх httpx
- LLM: GigaChat MAX → YandexGPT 5 Pro → mock fallback. **OpenAI/Anthropic не используем — это РФ-проект под B2G.**
- TTS: Yandex SpeechKit
- pytest + respx + pytest-asyncio (тесты)
- ruff + mypy (linting)
- GitHub Actions (CI: lint + tests + bandit + coverage + benchmark gate + gitleaks)

## Правила

1. Базовая ветка — `main`. Feature-branch: `devin/$(date +%s)-{slug}`.
2. Не амендить коммиты, не push --force в main, не --no-verify.
3. ruff и `npm run lint` проходят локально перед `git push`.
4. Все публичные функции и роуты — с типами и docstring (RU).
5. Тесты пишутся в том же PR. Coverage ≥ 70% (backend), не падает.
6. Никаких секретов в коде — только через `os.getenv` + `.env.example`.
7. Любой новый бот-канал = адаптер под `bots/core.py`, бизнес-логика в core.
8. **Telegram-бот ломать запрещено.** Все 9 тестов в `bot/tests/` должны проходить.
9. CI failure = блокер мержа. Если CI красный — чинить, не мерджить.
10. На каждый PR — обновление `README.md` или `docs/` (если фича требует объяснения).
11. После пуша — `git_pr create` → `git pr_checks` → ждать зелёного CI.

## Команды

```bash
# Backend
cd backend && poetry install
poetry run ruff check app/ tests/
poetry run pytest -q
poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=70

# Frontend
cd frontend && npm install
npm run lint
npm test
npm run build

# Bot (legacy Telegram, aiogram 3)
cd bot && pip install -r requirements.txt
ruff check .
pytest -q

# Bots core (multi-channel: VK / MAX / Web)
cd bots && pip install -e . && PYTHONPATH=.. pytest -q

# Бенчмарк (CI gate: MRR ≥ 0.85, Recall@5 ≥ 0.90)
cd backend && poetry run python -m app.benchmark > benchmark.json

# Persistence (опционально)
export CHITAI_STATE_DIR=/tmp/chitai-state
```

## Структура

```
backend/app/        — FastAPI, RAG, safety, privacy, audit, characters, challenge, …
backend/tests/      — pytest
frontend/src/       — React 18 + 9 табов (Куратор / Поиск / Тренажёр / Ментальная карта /
                      Пушкинская карта / Дашборд / Приватность / Аудит / Игра)
frontend/src/games/ — Brain Dash (three.js)
frontend/src/lib/   — sanitize.ts (DOMPurify XSS hardening)
bot/                — legacy Telegram aiogram 3
bots/               — multi-channel core + адаптеры (vk, max)
bots/adapters/      — VK long-poll, MAX HTTP API
evaluation/         — открытый RAG-бенчмарк (report.json reproducible)
docs/               — ROADMAP, PRODUCT, STATE, STRATEGY, PROMPTS, DEV_KIT,
                      STUDY_MODE_SPEC, GAMES_SPEC, pitch/
00_…13_/            — бизнес-документация (заявка, презентация, питч, бренд, юр.пакет,
                      методички, прототип, маркетинг, B2G продажи, гранты, пилот, FAQ,
                      письма поддержки)
.github/workflows/  — CI
```

## Перед коммитом

```bash
cd backend && poetry run ruff check app/ tests/ && poetry run pytest -q
cd ../frontend && npm run lint && npm test
cd ../bots && PYTHONPATH=.. pytest -q
```
